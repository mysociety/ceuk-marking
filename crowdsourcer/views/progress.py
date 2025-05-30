import csv
import logging
from datetime import datetime

from django.contrib.auth.mixins import UserPassesTestMixin
from django.contrib.auth.models import User
from django.db.models import Count, F, FloatField, OuterRef, Subquery
from django.db.models.functions import Cast
from django.http import HttpResponse
from django.utils.timezone import make_aware
from django.views.generic import ListView

from crowdsourcer.models import (
    Assigned,
    Marker,
    PublicAuthority,
    Question,
    Response,
    ResponseType,
    Section,
)
from crowdsourcer.views.base import (
    BaseAllSectionProgressView,
    BaseAuthorityAssignmentView,
    BaseSectionProgressView,
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


class AllSectionProgressView(BaseAllSectionProgressView):
    pass


class SectionProgressView(BaseSectionProgressView):
    pass


class BaseAllAuthorityProgressView(UserPassesTestMixin, ListView):
    template_name = "crowdsourcer/all_authority_progress.html"
    model = PublicAuthority
    context_object_name = "authorities"
    types = ["volunteer", "national_volunteer"]
    stage = "First Mark"
    page_title = "Progress"
    url_pattern = "authority_progress"

    def test_func(self):
        return self.request.user.is_superuser

    def get_queryset(self):
        response_type = ResponseType.objects.get(type=self.stage)
        qs = (
            PublicAuthority.objects.filter(
                marking_session=self.request.current_session,
                questiongroup__marking_session=self.request.current_session,
            )
            .annotate(
                num_questions=Subquery(
                    Question.objects.filter(
                        questiongroup=OuterRef("questiongroup"),
                        section__marking_session=self.request.current_session,
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
                        question__questiongroup=OuterRef("questiongroup"),
                        question__section__marking_session=self.request.current_session,
                        authority=OuterRef("pk"),
                        response_type=response_type,
                        question__how_marked__in=self.types,
                    )
                    .exclude(id__in=Response.null_responses(stage_name=self.stage))
                    .values("authority")
                    .annotate(response_count=Count("question_id", distinct=True))
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

        if self.request.current_session.entity_name is not None:
            self.page_title = (
                f"{self.request.current_session.entity_name}s {self.page_title}"
            )
        else:
            self.page_title = f"Councils {self.page_title}"

        context["councils"] = council_totals
        context["authorities"] = authorities
        context["page_title"] = self.page_title
        context["url_pattern"] = self.url_pattern

        return context


class AllAuthorityProgressView(BaseAllAuthorityProgressView):
    pass


class BaseAuthorityProgressView(UserPassesTestMixin, ListView):
    template_name = "crowdsourcer/authority_progress.html"
    model = Section
    context_object_name = "sections"
    types = ["volunteer", "national_volunteer"]
    stage = "First Mark"
    url_pattern = "authority_question_edit"
    ignore_read_only = True

    def test_func(self):
        return self.request.user.is_superuser

    def get_queryset(self):
        return Section.objects.filter(marking_session=self.request.current_session)

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
            if self.ignore_read_only:
                questions = questions.exclude(read_only=True)

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
                        .exclude(id__in=Response.null_responses(stage_name=self.stage))
                        .values("authority")
                        .annotate(response_count=Count("question_id", distict=True))
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
        context["url_pattern"] = self.url_pattern

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

        # XXX need to show stage on list
        sections = Section.objects.filter(
            marking_session=self.request.current_session,
            id__in=Assigned.objects.filter(user=user).values_list("section", flat=True),
        )

        return sections

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        sections = context["sections"]

        user = User.objects.get(id=self.kwargs["id"])
        progress = []

        types = {
            "First Mark": Question.VOLUNTEER_TYPES,
            "Right of Reply": Question.VOLUNTEER_TYPES,
            "Audit": ["volunteer", "national_volunteer", "foi"],
        }

        for section in sections:
            section_details = {
                "section": section,
                "totals": {"total": 0, "complete": 0},
                "responses": {},
            }
            for rt in ResponseType.objects.all():
                assigned = Assigned.objects.filter(
                    user=user,
                    section=section,
                    response_type=rt,
                ).values_list("authority", flat=True)

                authorities = (
                    PublicAuthority.objects.filter(id__in=assigned)
                    .annotate(
                        num_questions=Subquery(
                            Question.objects.filter(
                                section=section,
                                questiongroup=OuterRef("questiongroup"),
                                how_marked__in=types[rt.type],
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
                                question__questiongroup=OuterRef("questiongroup"),
                                authority=OuterRef("pk"),
                                response_type=rt,
                                question__how_marked__in=types[rt.type],
                            )
                            .exclude(id__in=Response.null_responses(stage_name=rt.type))
                            .values("authority")
                            .annotate(
                                response_count=Count("question_id", distinct=True)
                            )
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

                if rt.type == "First Mark":
                    authority_url_name = "authority_question_edit"
                elif rt.type == "Audit":
                    authority_url_name = "authority_audit"
                section_details["responses"][rt.type] = {
                    "authorities": authorities,
                    "totals": council_totals,
                    "authority_url_name": authority_url_name,
                }
                section_details["totals"]["total"] += council_totals["total"]
                section_details["totals"]["complete"] += council_totals["complete"]

            progress.append(section_details)

        if self.request.current_stage.type == "First Mark":
            authority_url_name = "authority_question_edit"
        elif self.request.current_stage.type == "Audit":
            authority_url_name = "authority_audit"

        context["user"] = user
        context["sections"] = progress
        context["page_title"] = "Volunteer Progress"
        context["authority_url_name"] = authority_url_name

        return context


class VolunteerProgressCSVView(UserPassesTestMixin, OverviewView):
    def test_func(self):
        return self.request.user.is_superuser

    def get_queryset(self):
        assigned = Assigned.objects.filter(
            marking_session=self.request.current_session,
        )
        if self.request.GET.get("show_all") != "1":
            assigned = assigned.filter(
                user__is_active=True,
                active=True,
            )
        return assigned

    def render_to_response(self, context, **response_kwargs):
        response = HttpResponse(content_type="text/csv")
        writer = csv.writer(response)
        headers = [
            "username",
            "section",
            "stage",
            "councils_assigned",
            "councils_started",
            "councils_completed",
        ]
        writer.writerow(headers)
        for stats in context["progress"]:
            a = stats["assignment"]
            section = "No section assigned"
            stage = "No stage assigned"
            if a.section is not None:
                section = a.section.title
            if a.response_type is not None:
                stage = a.response_type.type
            row = [
                a.user.username,
                section,
                stage,
                stats["total"],
                stats["started"],
                stats["complete"],
            ]
            writer.writerow(row)
        return response


class AuthorityAssignmentView(BaseAuthorityAssignmentView):
    pass


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
    page_title = "Right of Reply Progress"


class AuthorityLoginReport(UserPassesTestMixin, ListView):
    template_name = "crowdsourcer/authority_login_report.html"
    model = PublicAuthority
    context_object_name = "authorities"

    def test_func(self):
        return self.request.user.is_superuser

    def get_queryset(self):
        sd = self.request.current_session.start_date
        start_date = make_aware(datetime(sd.year, sd.month, sd.day))
        authorities = (
            PublicAuthority.objects.filter(
                marking_session=self.request.current_session,
                questiongroup__marking_session=self.request.current_session,
            )
            .annotate(
                has_logged_in=Subquery(
                    Marker.objects.filter(
                        authority=OuterRef("pk"),
                        response_type__type="Right of Reply",
                        marking_session=self.request.current_session,
                        user__last_login__gt=start_date,
                    )
                    .order_by("-user__last_login")
                    .values("user__last_login")[:1]
                ),
                multi_has_logged_in=Subquery(
                    Assigned.objects.filter(
                        authority=OuterRef("pk"),
                        marking_session=self.request.current_session,
                        user__marker__response_type__type="Right of Reply",
                        user__last_login__gt=start_date,
                    )
                    .order_by("-user__last_login")
                    .values("user__last_login")[:1]
                ),
            )
            .order_by("has_logged_in", "name")
        )

        return authorities


class AllSectionChallengeView(UserPassesTestMixin, ListView):
    template_name = "crowdsourcer/all_section_challenge.html"
    model = Section
    context_object_name = "sections"

    def test_func(self):
        return self.request.user.is_superuser

    def get_queryset(self):
        return Section.objects.filter(marking_session=self.request.current_session)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        types = ["volunteer", "national_volunteer", "foi"]
        response_types = ResponseType.objects.get(type="Right of Reply")

        progress = {}
        for section in context["sections"]:
            questions = Question.objects.filter(section=section, how_marked__in=types)
            question_list = list(questions.values_list("id", flat=True))
            authorities = (
                PublicAuthority.response_counts(
                    question_list,
                    section.title,
                    self.request.user,
                    self.request.current_session,
                    response_type=response_types,
                    question_types=types,
                    right_of_reply=True,
                )
                .annotate(
                    num_challenges=Subquery(
                        Response.objects.filter(
                            authority=OuterRef("pk"),
                            question__in=question_list,
                            response_type=response_types,
                            agree_with_response=False,
                        )
                        .values("authority")
                        .annotate(response_count=Count("question_id", distict=True))
                        .values("response_count")
                    )
                )
                .distinct()
            )

            total = 0
            complete = 0
            started = 0
            challenges = 0
            for authority in authorities:
                total = total + 1
                if authority.num_responses is not None and authority.num_responses > 0:
                    started = started + 1
                if authority.num_responses == authority.num_questions:
                    complete = complete + 1
                if authority.num_challenges is not None:
                    challenges = challenges + authority.num_challenges

            progress[section.title] = {
                "total": total,
                "complete": complete,
                "started": started,
                "challenges": challenges,
            }

        context["page_title"] = "Section Challenges"
        context["progress"] = progress

        return context


class AuthorityContactCSVView(UserPassesTestMixin, ListView):
    context_object_name = "markers"

    def test_func(self):
        return self.request.user.is_superuser

    def get_queryset(self):
        return Marker.objects.filter(
            response_type__type="Right of Reply",
            marking_session=self.request.current_session,
        ).select_related("user")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        markers = context["markers"]
        contacts = []
        for marker in markers:
            if marker.authority:
                contacts.append(
                    {
                        "council": marker.authority.name,
                        "email": marker.user.username,
                        "name": f"{marker.user.first_name} {marker.user.last_name}",
                    }
                )
            assigned = Assigned.objects.filter(
                user=marker.user, marking_session=self.request.current_session
            ).all()
            if assigned:
                for assignment in assigned:
                    council_name = "No authority assigned"
                    if assignment.authority:
                        council_name = assignment.authority.name
                    contacts.append(
                        {
                            "council": council_name,
                            "email": marker.user.username,
                            "name": f"{marker.user.first_name} {marker.user.last_name}",
                        }
                    )

        context["contacts"] = contacts
        return context

    def render_to_response(self, context, **response_kwargs):
        response = HttpResponse(
            content_type="text/csv",
            headers={
                "Content-Disposition": 'attachment; filename="grace_authority_contacts.csv"'
            },
        )
        writer = csv.writer(response)
        headers = ["council", "email", "name"]
        writer.writerow(headers)
        for contact in context["contacts"]:
            row = [
                contact["council"],
                contact["email"],
                contact["name"],
            ]
            writer.writerow(row)
        return response


# Audit progress


class AuditAuthorityAssignmentView(BaseAuthorityAssignmentView):
    stage = "Audit"


class AuditAllAuthorityProgressView(BaseAllAuthorityProgressView):
    template_name = "crowdsourcer/all_authority_progress.html"
    model = PublicAuthority
    context_object_name = "authorities"
    types = ["volunteer", "national_volunteer", "foi"]
    stage = "Audit"
    page_title = "Audit Progress"
    url_pattern = "audit_authority_progress"


class AuditAuthorityProgressView(BaseAuthorityProgressView):
    template_name = "crowdsourcer/authority_progress.html"
    model = Section
    context_object_name = "sections"
    types = ["volunteer", "national_volunteer", "foi"]
    stage = "Audit"
    url_pattern = "authority_audit"


class AuditAllSectionProgressView(BaseAllSectionProgressView):
    types = ["volunteer", "national_volunteer", "foi"]
    response_type = "Audit"
    url_pattern = "audit_section_progress"


class AuditSectionProgressView(BaseSectionProgressView):
    types = ["volunteer", "national_volunteer", "foi"]
    response_type = "Audit"
    url_pattern = "authority_audit"
