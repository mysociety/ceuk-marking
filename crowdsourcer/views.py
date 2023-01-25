from django.core.exceptions import PermissionDenied
from django.db.models import Count, F, FloatField, OuterRef, Subquery
from django.db.models.functions import Cast
from django.urls import reverse
from django.views.generic import DetailView, ListView, TemplateView
from django.views.generic.base import RedirectView
from django.views.generic.edit import CreateView, UpdateView

from crowdsourcer.forms import ResponseForm, ResponseFormset
from crowdsourcer.models import (
    Assigned,
    Option,
    PublicAuthority,
    Question,
    Response,
    ResponseType,
    Section,
)


class StatusPage(TemplateView):
    template_name = "crowdsourcer/status.html"


class OverviewView(ListView):
    template_name = "crowdsourcer/assignments.html"
    model = Assigned
    context_object_name = "assignments"

    def get_queryset(self):
        user = self.request.user
        if user.is_anonymous:
            return None

        qs = Assigned.objects.all()
        if user.is_superuser is False:
            qs = qs.filter(user=user)

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.user.is_anonymous:
            context["show_login"] = True
            return context

        context["show_users"] = self.request.user.is_superuser

        assignments = (
            context["assignments"]
            .distinct("user_id", "section_id")
            .select_related("section")
        )

        progress = []
        question_cache = {}
        for assignment in assignments:
            if question_cache.get(assignment.section_id, None) is not None:
                question_list = question_cache[assignment.section_id]
            else:
                questions = Question.objects.filter(
                    section=assignment.section, how_marked__in=Question.VOLUNTEER_TYPES
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
                    user=assignment.user_id, section=assignment.section_id
                ).values_list("authority_id", flat=True)
                args.append(authorities)

            response_counts = PublicAuthority.response_counts(*args).distinct()

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

            context["page_title"] = "Assignments"

        return context


class AuthorityProgressView(ListView):
    template_name = "crowdsourcer/authority_progress.html"
    model = PublicAuthority
    context_object_name = "authorities"

    def get_queryset(self):
        qs = (
            PublicAuthority.objects.all()
            .annotate(
                num_questions=Subquery(
                    Question.objects.filter(
                        questiongroup=OuterRef("questiongroup"),
                        how_marked__in=Question.VOLUNTEER_TYPES,
                    )
                    .values("questiongroup")
                    .annotate(num_questions=Count("pk"))
                    .values("num_questions")
                ),
            )
            .annotate(
                num_responses=Subquery(
                    Response.objects.filter(
                        authority=OuterRef("pk"),
                    )
                    .values("authority")
                    .annotate(response_count=Count("pk"))
                    .values("response_count")
                )
            )
            .annotate(
                qs_left=Cast(F("num_responses"), FloatField())
                / Cast(F("num_questions"), FloatField())
            )
        )

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        authorities = context["authorities"]
        sort_order = self.request.GET.get("sort", None)
        if sort_order is None or sort_order != "asc":
            authorities = authorities.order_by(
                F("qs_left").desc(nulls_last=True), "name"
            )

        else:
            authorities = authorities.order_by(
                F("qs_left").asc(nulls_first=True), "name"
            )

        council_totals = {"total": 0, "complete": 0}

        for a in authorities:
            council_totals["total"] = council_totals["total"] + 1
            if a.num_questions == a.num_responses:
                council_totals["complete"] = council_totals["complete"] + 1

        context["councils"] = council_totals
        context["authorities"] = authorities
        context["page_title"] = "Authorities Progress"

        return context


class SectionAuthorityList(ListView):
    template_name = "crowdsourcer/section_authority_list.html"
    model = Section
    context_object_name = "authorities"

    def get_queryset(self):
        if self.request.user.is_anonymous:
            return None

        if not Assigned.is_user_assigned(
            self.request.user,
            section=self.kwargs["section_title"],
        ):
            return None

        types = ["volunteer", "national_volunteer"]
        section = Section.objects.get(title=self.kwargs["section_title"])
        questions = Question.objects.filter(section=section, how_marked__in=types)

        question_list = list(questions.values_list("id", flat=True))

        assigned = None
        if not self.request.user.is_superuser:
            assigned = Assigned.objects.filter(
                user=self.request.user, section=section, authority__isnull=False
            ).values_list("authority__id", flat=True)

        authorities = PublicAuthority.response_counts(
            question_list, self.kwargs["section_title"], self.request.user, assigned
        )

        return authorities.order_by("name").distinct()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["section_title"] = self.kwargs["section_title"]
        context["page_title"] = context["section_title"]

        return context


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


class AuthoritySectionQuestions(TemplateView):
    template_name = "crowdsourcer/authority_questions.html"
    model = Response

    def get_initial_obj(self):
        authority = PublicAuthority.objects.get(name=self.kwargs["name"])
        questions = Question.objects.filter(
            section__title=self.kwargs["section_title"],
            questiongroup=authority.questiongroup,
            how_marked__in=["volunteer", "national_volunteer"],
        ).order_by("number", "number_part")
        responses = Response.objects.filter(
            authority=authority, question__in=questions
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
            data["option"] = r.option
            data["public_notes"] = r.public_notes
            data["private_notes"] = r.private_notes

            initial[r.question.id] = data

        return initial

    def get_form(self):
        if self.request.POST:
            formset = ResponseFormset(
                self.request.POST, initial=list(self.get_initial_obj().values())
            )
        else:
            formset = ResponseFormset(initial=list(self.get_initial_obj().values()))
        return formset

    def check_permissions(self):
        if self.request.user.is_anonymous:
            raise PermissionDenied

        if not Assigned.is_user_assigned(
            self.request.user,
            authority=self.kwargs["name"],
            section=self.kwargs["section_title"],
        ):
            raise PermissionDenied

    def get(self, *args, **kwargs):
        self.check_permissions()
        return super().get(*args, **kwargs)

    def post(self, *args, **kwargs):
        self.check_permissions()
        formset = self.get_form()
        rt = ResponseType.objects.get(type="First Mark")
        if formset.is_valid():
            for form in formset:
                cleaned_data = form.cleaned_data
                if (
                    cleaned_data.get("option", None) is not None
                    or len(list(cleaned_data.get("multi_option", None))) > 0
                ):
                    form.instance.response_type = rt
                    form.instance.user = self.request.user
                    form.save()
        else:
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
        ] = f"{context['authority_name']}: {context['section_title']}"

        return context


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
