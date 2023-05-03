import logging

from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.urls import reverse
from django.views.generic import ListView

from crowdsourcer.forms import RORResponseFormset
from crowdsourcer.models import (
    Assigned,
    PublicAuthority,
    Question,
    Response,
    ResponseType,
    Section,
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
            sections = Section.objects.filter(title__contains="(CA)")
        else:
            sections = Section.objects.exclude(title__contains="(CA)")

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
        if self.request.user.is_anonymous:
            raise PermissionDenied

        authority = PublicAuthority.objects.get(name=self.kwargs["name"])
        user = self.request.user
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
