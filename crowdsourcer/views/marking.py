import logging

from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.urls import reverse
from django.views.generic import DetailView, ListView, TemplateView
from django.views.generic.base import RedirectView
from django.views.generic.edit import CreateView, UpdateView

from crowdsourcer.forms import ResponseForm
from crowdsourcer.mixins import CurrentStageMixin
from crowdsourcer.models import (
    Assigned,
    Option,
    PublicAuthority,
    Question,
    Response,
    ResponseType,
    Section,
)
from crowdsourcer.views.base import BaseQuestionView, BaseSectionAuthorityList

logger = logging.getLogger(__name__)


class StatusPage(TemplateView):
    template_name = "crowdsourcer/status.html"


class PrivacyPolicyView(TemplateView):
    template_name = "crowdsourcer/privacy.html"


class OverviewView(CurrentStageMixin, ListView):
    template_name = "crowdsourcer/assignments.html"
    model = Assigned
    context_object_name = "assignments"

    def dispatch(self, request, *args, **kwargs):
        user = self.request.user
        if hasattr(user, "marker"):
            url = None
            marker = user.marker
            # if a user only handles one council then they will have a council assigned
            # directly in the marker object directly show them the sections page as it
            # removes a step
            if (
                marker.response_type.type == "Right of Reply"
                and marker.authority is not None
            ):
                url = reverse(
                    "authority_ror_sections", kwargs={"name": marker.authority.name}
                )
            # some councils have shared back office staff so one person might be doing
            # the RoR for multiple councils in which case they need to see the assignment
            # screen
            elif marker.response_type.type == "Right of Reply":
                if Assigned.objects.filter(user=user).exists():
                    count = Assigned.objects.filter(user=user).count()
                    # however if they only have a single assignment still skip the
                    # assignments screen
                    if count == 1:
                        assignment = Assigned.objects.filter(user=user).first()
                        url = reverse(
                            "authority_ror_sections",
                            kwargs={"name": assignment.authority.name},
                        )
                    # if they have nothing assigned then it's fine to show then the blank
                    # no assignments screen so handle everything else
                    else:
                        url = reverse("authority_ror_authorities")

            if url is not None:
                return redirect(url)

        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        user = self.request.user
        if user.is_anonymous:
            return None

        qs = Assigned.objects.filter(
            section__isnull=False, response_type=self.current_stage
        )
        if user.is_superuser is False:
            qs = qs.filter(user=user)
        else:
            qs = qs.filter(user__is_active=True)

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.user.is_anonymous:
            context["show_login"] = True
            return context

        user = self.request.user
        context["show_users"] = user.is_superuser

        assignments = (
            context["assignments"]
            .distinct("user_id", "section_id")
            .select_related("section")
        )

        types = Question.VOLUNTEER_TYPES
        if self.current_stage.type == "Audit":
            types = ["volunteer", "national_volunteer", "foi"]

        progress = []
        question_cache = {}
        for assignment in assignments:
            if question_cache.get(assignment.section_id, None) is not None:
                question_list = question_cache[assignment.section_id]
            else:
                questions = Question.objects.filter(
                    section=assignment.section, how_marked__in=types
                )
                question_list = list(questions.values_list("id", flat=True))
                question_cache[assignment.section_id] = question_list

            args = [
                question_list,
                assignment.section.title,
                assignment.user,
            ]
            if assignment.authority_id is not None:
                authorities = Assigned.objects.filter(
                    user=assignment.user_id,
                    section=assignment.section_id,
                    response_type=self.current_stage,
                ).values_list("authority_id", flat=True)
                args.append(authorities)

            response_counts = PublicAuthority.response_counts(
                *args, question_types=types, response_type=self.current_stage
            ).distinct()

            total = 0
            complete = 0

            for count in response_counts:
                total += 1
                if count.num_responses == count.num_questions:
                    complete += 1
            progress.append(
                {"assignment": assignment, "complete": complete, "total": total}
            )

            context["progress"] = progress

            user_stage = self.current_stage.type
            if hasattr(user, "marker"):
                if user.marker.response_type:
                    user_stage = user.marker.response_type.type

            if user_stage == "First Mark":
                section_link = "section_authorities"
            elif user_stage == "Audit":
                section_link = "audit_section_authorities"

            context["page_title"] = "Assignments"
            context["section_link"] = section_link

        return context


class SectionAuthorityList(BaseSectionAuthorityList):
    pass


class SectionQuestionList(ListView):
    template_name = "crowdsourcer/section_question_list.html"
    model = Section
    context_object_name = "questions"

    def get_queryset(self):
        if self.request.user.is_anonymous:
            return None

        section = Section.objects.get(title=self.kwargs["section_title"])
        return Question.objects.filter(section=section).order_by("number")


class SectionQuestionAuthorityList(ListView):
    template_name = "crowdsourcer/section_question_authority_list.html"
    model = Question
    context_object_name = "authorities"

    def get_queryset(self):
        if self.request.user.is_anonymous:
            return None

        question = Question.objects.get(
            number=self.kwargs["number"], section__title=self.kwargs["section_title"]
        )
        return PublicAuthority.objects.filter(
            questiongroup__question=question
        ).order_by("name")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        question = Question.objects.get(
            number=self.kwargs["number"], section__title=self.kwargs["section_title"]
        )
        context["question"] = question
        return context


class AuthoritySectionQuestions(BaseQuestionView):
    template_name = "crowdsourcer/authority_questions.html"

    def check_permissions(self):
        if self.request.user.is_anonymous:
            raise PermissionDenied

        if not Assigned.is_user_assigned(
            self.request.user,
            authority=self.kwargs["name"],
            section=self.kwargs["section_title"],
        ):
            raise PermissionDenied

    def process_form(self, form):
        rt = ResponseType.objects.get(type="First Mark")
        cleaned_data = form.cleaned_data
        if (
            cleaned_data.get("option", None) is not None
            or len(list(cleaned_data.get("multi_option", None))) > 0
        ):
            form.instance.response_type = rt
            form.instance.user = self.request.user
            form.save()
            logger.debug(f"saved form {form.prefix}")
        else:
            logger.debug(f"did not save form {form.prefix}")
            logger.debug(
                f"option is {cleaned_data.get('option', None)}, multi is {cleaned_data.get('multi_option', None)}"
            )


class AuthorityQuestion(RedirectView):
    def get_redirect_url(self, *args, **kwargs):
        kwargs = {
            "name": self.kwargs["name"],
            "section_title": self.kwargs["section_title"],
            "number": self.kwargs["number"],
        }
        if not Assigned.is_user_assigned(
            self.request.user,
            authority=self.kwargs["name"],
            section=self.kwargs["section_title"],
        ):
            return reverse("authority_question_view", kwargs=kwargs)

        try:
            Response.objects.get(
                authority__name=self.kwargs["name"],
                question__number=self.kwargs["number"],
                question__section__title=self.kwargs["section_title"],
            )
        except Response.DoesNotExist:
            return reverse("authority_question_answer", kwargs=kwargs)

        return reverse("authority_question_edit", kwargs=kwargs)


class AuthorityQuestionAnswer(CreateView):
    template_name = "crowdsourcer/authority_question.html"
    model = Response
    form_class = ResponseForm

    def get_initial(self):
        if not Assigned.is_user_assigned(
            self.request.user,
            authority=self.kwargs["name"],
            section=self.kwargs["section_title"],
        ):
            raise PermissionDenied

        authority = PublicAuthority.objects.get(name=self.kwargs["name"])
        question = Question.objects.get(
            number=self.kwargs["number"], section__title=self.kwargs["section_title"]
        )

        return {
            "question": question,
            "authority": authority,
        }

    def form_valid(self, form):
        form.instance.user = self.request.user
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        form = context["form"]
        question = form.initial["question"]
        context["options"] = Option.objects.filter(question=question)
        form.fields["option"].choices = [
            (c.id, c.description) for c in Option.objects.filter(question=question)
        ]
        context["form"] = form

        context["authority"] = form.initial["authority"]

        return context


class AuthorityQuestionView(DetailView):
    template_name = "crowdsourcer/authority_question_view.html"
    model = Response
    context_object_name = "response"

    def get_object(self):
        response = Response.objects.get(
            authority__name=self.kwargs["name"],
            question__number=self.kwargs["number"],
            question__section__title=self.kwargs["section_title"],
        )

        return response


class AuthorityQuestionEdit(UpdateView):
    template_name = "crowdsourcer/authority_question.html"
    model = Response
    form_class = ResponseForm

    def get_object(self):
        if not Assigned.is_user_assigned(
            self.request.user,
            authority=self.kwargs["name"],
            section=self.kwargs["section_title"],
        ):
            raise PermissionDenied
        response = Response.objects.get(
            authority__name=self.kwargs["name"],
            question__number=self.kwargs["number"],
            question__section__title=self.kwargs["section_title"],
        )

        return response

    def form_valid(self, form):
        form.instance.user = self.request.user
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        form = context["form"]
        question = form.initial["question"]
        context["options"] = Option.objects.filter(question=question)
        form.fields["option"].choices = [
            (c.id, c.description) for c in Option.objects.filter(question=question)
        ]
        context["form"] = form

        context["authority"] = form.initial["authority"]

        return context
