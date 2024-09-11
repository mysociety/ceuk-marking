import csv
import logging
from collections import defaultdict

from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.views.generic import ListView

from crowdsourcer.forms import RORResponseFormset
from crowdsourcer.models import (
    Assigned,
    Marker,
    PublicAuthority,
    Question,
    Response,
    ResponseType,
    Section,
    SessionProperties,
)
from crowdsourcer.views.base import BaseQuestionView

logger = logging.getLogger(__name__)


class AuthorityRORList(ListView):
    template_name = "crowdsourcer/authority_assigned_list.html"
    model = Assigned
    context_object_name = "assignments"

    def dispatch(self, request, *args, **kwargs):
        user = self.request.user
        if hasattr(user, "marker"):
            marker = user.marker
            if (
                marker.response_type.type == "Right of Reply"
                and marker.authority is not None
            ):
                url = reverse(
                    "authority_ror_sections", kwargs={"name": marker.authority.name}
                )
                return redirect(url)

        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        user = self.request.user
        if user.is_anonymous:
            return None

        qs = Assigned.objects.filter(user=user).order_by("authority__name")

        return qs


class AuthorityRORSectionList(ListView):
    template_name = "crowdsourcer/authority_section_list.html"
    model = Section
    context_object_name = "sections"

    def get_queryset(self):
        user = self.request.user

        if user.is_anonymous:
            raise PermissionDenied

        authority = PublicAuthority.objects.get(name=self.kwargs["name"])
        if user.is_superuser is False:
            if hasattr(user, "marker"):
                marker = user.marker
                if marker.response_type.type == "Right of Reply":
                    if (
                        marker.authority != authority
                        and not Assigned.objects.filter(
                            user=user, authority=authority, section__isnull=True
                        ).exists()
                    ):
                        raise PermissionDenied
                else:
                    raise PermissionDenied

            else:
                raise PermissionDenied

        if authority.type == "COMB":
            sections = Section.objects.filter(
                title__contains="(CA)", marking_session=self.request.current_session
            )
        else:
            sections = Section.objects.exclude(title__contains="(CA)").filter(
                marking_session=self.request.current_session
            )

        return sections

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["authority_name"] = self.kwargs["name"]

        sections = context["sections"]
        question_types = ["volunteer", "national_volunteer", "foi"]

        response_type = ResponseType.objects.get(type="Right of Reply")
        for section in sections:
            questions = Question.objects.filter(
                section=section,
                how_marked__in=question_types,
            )
            question_list = list(questions.values_list("id", flat=True))

            authority = PublicAuthority.objects.get(name=context["authority_name"])
            args = [
                question_list,
                section.title,
                self.request.user,
                self.request.current_session,
                [authority.id],
            ]

            response_counts = PublicAuthority.response_counts(
                *args, response_type=response_type, question_types=question_types
            ).distinct()

            section.complete = 0
            section.total = 0
            if response_counts.exists():
                section.complete = response_counts.first().num_responses
                section.total = response_counts.first().num_questions
                if section.complete is None:
                    section.complete = 0

        context["ror_user"] = True
        context["has_properties"] = SessionProperties.objects.filter(
            marking_session=self.request.current_session, stage=response_type
        ).exists()
        return context


class AuthorityRORSectionQuestions(BaseQuestionView):
    template_name = "crowdsourcer/authority_ror_questions.html"
    model = Response
    formset = RORResponseFormset
    response_type = "Right of Reply"
    log_start = "ROR form"
    title_start = "Right of Reply - "
    how_marked_in = ["volunteer", "national_volunteer", "foi"]

    def get_initial_obj(self):
        initial = super().get_initial_obj()

        rt = ResponseType.objects.get(type="First Mark")
        responses = Response.objects.filter(
            authority=self.authority, question__in=self.questions, response_type=rt
        ).select_related("question")

        for r in responses:
            data = initial[r.question.id]
            data["original_response"] = r

            initial[r.question.id] = data

        return initial

    def check_permissions(self):
        denied = True
        authority = PublicAuthority.objects.get(name=self.kwargs["name"])
        user = self.request.user

        if user.is_anonymous:
            raise PermissionDenied

        if (
            user.is_superuser
            or Marker.objects.filter(
                user=user,
                response_type=self.rt,
                marking_session=self.request.current_session,
                authority=authority,
            ).exists()
            or Assigned.objects.filter(
                user=user,
                response_type=self.rt,
                authority=authority,
                section__isnull=True,
                marking_session=self.request.current_session,
            ).exists()
        ):
            denied = False

        if denied:
            raise PermissionDenied

    def process_form(self, form):
        rt = ResponseType.objects.get(type="Right of Reply")
        cleaned_data = form.cleaned_data
        if cleaned_data.get("agree_with_response", None) is not None:
            form.instance.response_type = rt
            form.instance.user = self.request.user
            form.save()
            logger.debug(f"saved form {form.prefix}")
        elif form.initial.get("id", None) is not None:
            form.save()
            logger.debug(f"saved blank form {form.prefix}")
        else:
            logger.debug(f"did not save form {form.prefix}")
            logger.debug(
                f"agree_with_response is {cleaned_data.get('agree_with_response', None)}"
            )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["ror_user"] = True
        return context


class AuthorityRORCSVView(ListView):
    context_object_name = "responses"

    def get_queryset(self):
        user = self.request.user

        rt = ResponseType.objects.get(type="Right of Reply")
        if user.is_superuser:
            authority_name = self.kwargs["name"]
            authority = PublicAuthority.objects.get(name=authority_name)
        else:
            authority = self.request.user.marker.authority

        self.authority = authority

        if authority is not None:
            return (
                Response.objects.filter(
                    question__section__marking_session=self.request.current_session,
                    response_type=rt,
                    authority=authority,
                )
                .select_related("question", "question__section")
                .order_by(
                    "question__section__title",
                    "question__number",
                    "question__number_part",
                )
            )

        return None

    def get_first_mark_responses(self):
        rt = ResponseType.objects.get(type="First Mark")
        responses = (
            Response.objects.filter(
                question__section__marking_session=self.request.current_session,
                response_type=rt,
                authority=self.authority,
            )
            .select_related("question", "question__section")
            .order_by(
                "question__section__title",
                "question__number",
                "question__number_part",
            )
        )

        by_section = defaultdict(dict)

        for r in responses:
            by_section[r.question.section.title][
                r.question.number_and_part
            ] = r.option.description

        return by_section

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        rows = []
        rows.append(
            [
                "section",
                "question_no",
                "question",
                "first_mark_response",
                "agree_with_mark",
                "council_response",
                "council_evidence",
                "council_page_number",
                "council_notes",
            ]
        )

        first_mark_responses = self.get_first_mark_responses()

        for response in context["responses"]:
            first_mark_response = ""
            if first_mark_responses.get(
                response.question.section.title
            ) and first_mark_responses[response.question.section.title].get(
                response.question.number_and_part
            ):
                first_mark_response = first_mark_responses[
                    response.question.section.title
                ][response.question.number_and_part]
            rows.append(
                [
                    response.question.section.title,
                    response.question.number_and_part,
                    response.question.description,
                    first_mark_response,
                    "Yes" if response.agree_with_response else "No",
                    response.option,
                    ",".join(response.evidence_links),
                    response.page_number,
                    response.evidence,
                ]
            )

        context["authority"] = self.authority.name
        context["rows"] = rows

        return context

    def render_to_response(self, context, **response_kwargs):
        filename = f"{self.request.current_session.label}_{context['authority']}_Right_of_Reply.csv"
        response = HttpResponse(
            content_type="text/csv",
            headers={"Content-Disposition": 'attachment; filename="' + filename + '"'},
        )
        writer = csv.writer(response)
        for row in context["rows"]:
            writer.writerow(row)
        return response
