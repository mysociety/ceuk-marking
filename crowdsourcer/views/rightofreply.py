import logging

from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.urls import reverse
from django.views.generic import ListView, TemplateView

from crowdsourcer.forms import RORResponseFormset
from crowdsourcer.models import (
    Assigned,
    PublicAuthority,
    Question,
    Response,
    ResponseType,
    Section,
)

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


class AuthorityRORSectionQuestions(TemplateView):
    template_name = "crowdsourcer/authority_ror_questions.html"
    model = Response

    def get_initial_obj(self):
        rt = ResponseType.objects.get(type="Right of Reply")
        authority = PublicAuthority.objects.get(name=self.kwargs["name"])
        questions = Question.objects.filter(
            section__title=self.kwargs["section_title"],
            questiongroup=authority.questiongroup,
            how_marked__in=["volunteer", "national_volunteer", "foi"],
        ).order_by("number", "number_part")
        responses = Response.objects.filter(
            authority=authority, question__in=questions, response_type=rt
        ).select_related("question")

        initial = {}
        for q in questions.all():
            data = {
                "authority": authority,
                "question": q,
            }
            initial[q.id] = data

        for r in responses:
            data = initial[r.question.id]
            data["id"] = r.id
            data["private_notes"] = r.private_notes

            initial[r.question.id] = data

        rt = ResponseType.objects.get(type="First Mark")
        responses = Response.objects.filter(
            authority=authority, question__in=questions, response_type=rt
        ).select_related("question")

        for r in responses:
            data = initial[r.question.id]
            data["original_response"] = r

            initial[r.question.id] = data

        return initial

    def get_form(self):
        if self.request.POST:
            formset = RORResponseFormset(
                self.request.POST, initial=list(self.get_initial_obj().values())
            )
        else:
            formset = RORResponseFormset(initial=list(self.get_initial_obj().values()))
        return formset

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

    def get(self, *args, **kwargs):
        self.check_permissions()
        return super().get(*args, **kwargs)

    def post(self, *args, **kwargs):
        self.check_permissions()
        section_title = self.kwargs.get("section_title", "")
        authority = self.kwargs.get("name", "")
        logger.debug(
            f"ROR form post from {self.request.user.email} for {authority}/{section_title}"
        )
        logger.debug(f"post data is {self.request.POST}")

        formset = self.get_form()
        rt = ResponseType.objects.get(type="Right of Reply")
        if formset.is_valid():
            logger.debug("form IS VALID")
            for form in formset:
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
        else:
            logger.debug(f"form NOT VALID, errors are {formset.errors}")
            return self.render_to_response(self.get_context_data(form=formset))

        context = self.get_context_data()
        context["message"] = "Your answers have been saved."
        return self.render_to_response(context)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["form"] = self.get_form()
        context["section_title"] = self.kwargs.get("section_title", "")
        context["authority"] = PublicAuthority.objects.get(
            name=self.kwargs.get("name", "")
        )
        context["authority_name"] = self.kwargs.get("name", "")
        context[
            "page_title"
        ] = f"Right of Reply - {context['authority_name']}: {context['section_title']}"

        context["ror_user"] = True

        return context
