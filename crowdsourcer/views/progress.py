import logging

from django.contrib.auth.mixins import UserPassesTestMixin
from django.contrib.auth.models import User
from django.db.models import Count, F, FloatField, OuterRef, Subquery
from django.db.models.functions import Cast
from django.views.generic import ListView

from crowdsourcer.models import (
    Assigned,
    PublicAuthority,
    Question,
    Response,
    ResponseType,
    Section,
)
from crowdsourcer.views.marking import OverviewView

logger = logging.getLogger(__name__)


class InactiveOverview(OverviewView):
    def get_queryset(self):
        user = self.request.user
        if user.is_superuser is False:
            return None

        qs = Assigned.objects.all()
        if user.is_superuser is False:
            qs = qs.filter(user=user)
        else:
            qs = qs.filter(user__is_active=False)

        return qs


class AllSectionProgressView(UserPassesTestMixin, ListView):
    template_name = "crowdsourcer/all_section_progress.html"
    model = Section
    context_object_name = "sections"

    def test_func(self):
        return self.request.user.is_superuser

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        types = ["volunteer", "national_volunteer"]

        progress = {}
        for section in context["sections"]:
            questions = Question.objects.filter(section=section, how_marked__in=types)
            question_list = list(questions.values_list("id", flat=True))
            authorities = PublicAuthority.response_counts(
                question_list, section.title, self.request.user
            ).distinct()

            total = 0
            complete = 0
            started = 0
            for authority in authorities:
                total = total + 1
                if authority.num_responses is not None and authority.num_responses > 0:
                    started = started + 1
                if authority.num_responses == authority.num_questions:
                    complete = complete + 1

            progress[section.title] = {
                "total": total,
                "complete": complete,
                "started": started,
            }

        assigned = Section.objects.all().annotate(
            num_authorities=Subquery(
                Assigned.objects.filter(section=OuterRef("pk"))
                .values("section")
                .annotate(num_authorities=Count("pk"))
                .values("num_authorities")
            )
        )

        for section in assigned:
            progress[section.title]["assigned"] = section.num_authorities

        context["page_title"] = "Section Progress"
        context["progress"] = progress

        return context


class SectionProgressView(UserPassesTestMixin, ListView):
    template_name = "crowdsourcer/section_progress.html"
    model = Section
    context_object_name = "sections"

    def test_func(self):
        return self.request.user.is_superuser

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        types = ["volunteer", "national_volunteer"]
        section = Section.objects.get(title=self.kwargs["section_title"])
        questions = Question.objects.filter(section=section, how_marked__in=types)

        question_list = list(questions.values_list("id", flat=True))

        authorities = (
            PublicAuthority.response_counts(
                question_list, section.title, self.request.user
            )
            .distinct()
            .annotate(
                qs_left=Cast(F("num_responses"), FloatField())
                / Cast(F("num_questions"), FloatField())
            )
        )

        sort_order = self.request.GET.get("sort", None)
        if sort_order is None or sort_order != "asc":
            authorities = authorities.order_by(
                F("qs_left").desc(nulls_last=True), "name"
            )

        else:
            authorities = authorities.order_by(
                F("qs_left").asc(nulls_first=True), "name"
            )

        total = 0
        complete = 0
        for authority in authorities:
            total = total + 1
            if authority.num_responses == authority.num_questions:
                complete = complete + 1

        context["page_title"] = f"{section.title} Section Progress"
        context["section"] = section
        context["totals"] = {"total": total, "complete": complete}
        context["authorities"] = authorities

        return context


class BaseAllAuthorityProgressView(UserPassesTestMixin, ListView):
    template_name = "crowdsourcer/all_authority_progress.html"
    model = PublicAuthority
    context_object_name = "authorities"
    types = ["volunteer", "national_volunteer", "foi"]
    stage = "Right of Reply"
    page_title = "Authorities Progress"

    def test_func(self):
        return self.request.user.is_superuser

    def get_queryset(self):
        response_type = ResponseType.objects.get(type=self.stage)
        qs = (
            PublicAuthority.objects.all()
            .annotate(
                num_questions=Subquery(
                    Question.objects.filter(
                        questiongroup=OuterRef("questiongroup"),
                        how_marked__in=self.types,
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
                        response_type=response_type,
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
        context["page_title"] = self.page_title

        return context


class AllAuthorityProgressView(BaseAllAuthorityProgressView):
    pass


class BaseAuthorityProgressView(UserPassesTestMixin, ListView):
    template_name = "crowdsourcer/authority_progress.html"
    model = Section
    context_object_name = "sections"
    types = ["volunteer", "national_volunteer"]
    stage = "First Mark"

    def test_func(self):
        return self.request.user.is_superuser

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        name = self.kwargs["name"]
        progress = {}

        stage = ResponseType.objects.get(type=self.stage)
        sections = context["sections"]
        for section in sections:
            questions = Question.objects.filter(
                section=section, how_marked__in=self.types
            )
            question_list = list(questions.values_list("id", flat=True))
            qs = (
                PublicAuthority.objects.filter(name=name)
                .annotate(
                    num_questions=Subquery(
                        Question.objects.filter(
                            questiongroup=OuterRef("questiongroup"),
                            how_marked__in=self.types,
                            pk__in=question_list,
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
                            question__in=question_list,
                            response_type=stage,
                        )
                        .values("authority")
                        .annotate(response_count=Count("pk"))
                        .values("response_count")
                    )
                )
            )
            authority = qs.first()
            responses = authority.num_responses
            if responses is None:
                responses = 0
            progress[section.title] = {
                "responses": responses,
                "total": authority.num_questions,
            }

        context["sections"] = progress
        context["authority_name"] = name
        context["page_title"] = f"{name} Progress"

        return context


class AuthorityProgressView(BaseAuthorityProgressView):
    pass


class VolunteerProgressView(UserPassesTestMixin, ListView):
    template_name = "crowdsourcer/volunteer_progress.html"
    model = Section
    context_object_name = "sections"

    def test_func(self):
        return self.request.user.is_superuser

    def get_queryset(self):
        user = User.objects.get(id=self.kwargs["id"])

        sections = Section.objects.filter(
            id__in=Assigned.objects.filter(user=user).values_list("section", flat=True)
        )

        return sections

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        sections = context["sections"]

        user = User.objects.get(id=self.kwargs["id"])
        progress = []

        for section in sections:
            assigned = Assigned.objects.filter(user=user, section=section).values_list(
                "authority", flat=True
            )

            authorities = (
                PublicAuthority.objects.filter(id__in=assigned)
                .annotate(
                    num_questions=Subquery(
                        Question.objects.filter(
                            section=section,
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
                            question__section=section,
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

            progress.append(
                {
                    "section": section,
                    "authorities": authorities,
                    "totals": council_totals,
                }
            )

        context["user"] = user
        context["sections"] = progress
        context["page_title"] = "Volunteer Progress"

        return context


class AuthorityAssignmentView(UserPassesTestMixin, ListView):
    template_name = "crowdsourcer/authorities_assigned.html"
    model = PublicAuthority
    context_object_name = "authorities"

    def test_func(self):
        return self.request.user.is_superuser

    def get_queryset(self):
        qs = PublicAuthority.objects.all().annotate(
            num_sections=Subquery(
                Assigned.objects.filter(authority=OuterRef("pk"))
                .values("authority")
                .annotate(num_sections=Count("pk"))
                .values("num_sections")
            )
        )

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        authorities = context["authorities"]
        sort_order = self.request.GET.get("sort", None)
        do_not_mark_only = self.request.GET.get("do_not_mark_only", None)

        if do_not_mark_only is not None:
            authorities = authorities.filter(do_not_mark=True)

        if sort_order is None or sort_order != "asc":
            authorities = authorities.order_by(
                F("num_sections").desc(nulls_last=True), "name"
            )

        else:
            authorities = authorities.order_by(
                F("num_sections").asc(nulls_first=True), "name"
            )

        context["authorities"] = authorities
        context["do_not_mark_only"] = do_not_mark_only

        return context


# Right of reply progress
class AuthorityRoRProgressView(BaseAuthorityProgressView):
    template_name = "crowdsourcer/authority_ror_progress.html"
    types = ["volunteer", "national_volunteer", "foi"]
    stage = "Right of Reply"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        name = self.kwargs["name"]
        context["page_title"] = f"{name} Right of Reply Progress"
        return context


class AllAuthorityRoRProgressView(BaseAllAuthorityProgressView):
    template_name = "crowdsourcer/all_authority_ror_progress.html"
    types = ["volunteer", "national_volunteer", "foi"]
    stage = "Right of Reply"
    page_title = "Authorities Right of Reply Progress"
