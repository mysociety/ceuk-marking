import logging

from django.shortcuts import redirect
from django.urls import reverse
from django.views.generic import ListView, TemplateView

from crowdsourcer.models import (
    Assigned,
    MarkingSession,
    PublicAuthority,
    Question,
    Response,
    ResponseType,
)
from crowdsourcer.views.base import (
    BaseQuestionView,
    BaseResponseJSONView,
    BaseSectionAuthorityList,
)

logger = logging.getLogger(__name__)


class StatusPage(TemplateView):
    template_name = "crowdsourcer/status.html"


class PrivacyPolicyView(TemplateView):
    template_name = "crowdsourcer/privacy.html"


class OverviewView(ListView):
    template_name = "crowdsourcer/assignments.html"
    model = Assigned
    context_object_name = "assignments"

    def dispatch(self, request, *args, **kwargs):
        user = self.request.user
        if self.request.current_session is not None and hasattr(user, "marker"):
            session = None
            url = None
            marker = user.marker
            # if a user only handles one council then they will have a council assigned
            # directly in the marker object directly show them the sections page as it
            # removes a step

            sessions = marker.marking_session.filter(active=True).all()
            if len(sessions) == 1:
                session = marker.marking_session.first()
                if self.request.current_session != session:
                    url = reverse(
                        "session_urls:home", kwargs={"marking_session": session.label}
                    )

            if (
                marker.response_type.type == "Right of Reply"
                and marker.authority is not None
                and session is not None
            ):
                url = reverse(
                    "session_urls:authority_ror_sections",
                    kwargs={"name": marker.authority.name, "marking_session": session},
                )
            # some councils have shared back office staff so one person might be doing
            # the RoR for multiple councils in which case they need to see the assignment
            # screen
            elif marker.response_type.type == "Right of Reply":
                if Assigned.objects.filter(user=user).exists():
                    count = Assigned.objects.filter(
                        user=user, marking_session=self.request.current_session
                    ).count()
                    # however if they only have a single assignment still skip the
                    # assignments screen
                    if count == 1:
                        assignment = Assigned.objects.filter(
                            user=user, marking_session=self.request.current_session
                        ).first()
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
            section__isnull=False,
            active=True,
        )
        if user.has_perm("crowdsourcer.can_view_all_responses") is False:
            if hasattr(user, "marker"):
                m = user.marker
                qs = qs.filter(response_type=m.response_type)
            else:
                qs = qs.filter(response_type__type="First Mark")
            qs = qs.filter(user=user)
        else:
            if hasattr(user, "marker"):
                m = user.marker
                qs = qs.filter(response_type=m.response_type)

            qs = qs.filter(user__is_active=True)

        qs = qs.filter(marking_session=self.request.current_session)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.user.is_anonymous:
            context["show_login"] = True
            return context

        user = self.request.user
        context["show_users"] = user.is_superuser

        if self.request.current_session is None or self.request.current_stage is None:
            if user.is_superuser:
                context["setup_required"] = (
                    "You need to add a marking session with a request type in the admin."
                )
            else:
                context["setup_required"] = "This site is not set up yet."

            return context

        assignments = (
            context["assignments"]
            .distinct("user_id", "section_id", "response_type_id")
            .select_related("section", "response_type")
        )

        types = Question.VOLUNTEER_TYPES
        if self.request.current_stage.type == "Audit":
            types = ["volunteer", "national_volunteer", "foi"]

        first_mark = ResponseType.objects.get(type="First Mark")

        progress = []
        question_cache = {}
        for assignment in assignments:
            assignment_user = assignment.user
            if hasattr(assignment_user, "marker"):
                stage = assignment_user.marker.response_type
            else:
                stage = first_mark

            if question_cache.get(assignment.section_id, None) is not None:
                question_list = question_cache[assignment.section_id]
            else:
                questions = Question.objects.filter(
                    section=assignment.section, how_marked__in=types
                )
                question_list = list(questions.values_list("id", flat=True))
                question_cache[assignment.section_id] = question_list

            total = 0
            complete = 0

            if assignment.section is not None:
                args = [
                    question_list,
                    assignment.section.title,
                    assignment.user,
                    self.request.current_session,
                ]
                if assignment.authority_id is not None:
                    authorities = Assigned.objects.filter(
                        active=True,
                        user=assignment.user_id,
                        section=assignment.section_id,
                        response_type=stage,
                    ).values_list("authority_id", flat=True)
                    args.append(authorities)

                response_counts = PublicAuthority.response_counts(
                    *args, question_types=types, response_type=assignment.response_type
                ).distinct()

                for count in response_counts:
                    total += 1
                    if count.num_responses == count.num_questions:
                        complete += 1

            if assignment.response_type is None:
                section_link = "home"
            elif assignment.response_type.type == "First Mark":
                section_link = "section_authorities"
            elif assignment.response_type.type == "Audit":
                section_link = "audit_section_authorities"

            progress.append(
                {
                    "assignment": assignment,
                    "complete": complete,
                    "total": total,
                    "section_link": section_link,
                }
            )

        context["sessions"] = MarkingSession.objects.filter(active=True)
        context["progress"] = progress

        context["page_title"] = "Assignments"

        return context


class SectionAuthorityList(BaseSectionAuthorityList):
    pass


class AuthoritySectionQuestions(BaseQuestionView):
    template_name = "crowdsourcer/authority_questions.html"

    def get_template_names(self):
        if self.has_previous_questions:
            return ["crowdsourcer/authority_questions_with_previous.html"]
        else:
            return [self.template_name]

    def get_initial_obj(self):
        if self.kwargs["name"] == "Isles of Scilly":
            self.how_marked_in = [
                "volunteer",
                "national_volunteer",
                "foi",
                "national_data",
            ]

        initial = super().get_initial_obj()

        is_previous = Question.objects.filter(
            section__marking_session=self.request.current_session,
            section__title=self.kwargs["section_title"],
            questiongroup=self.authority.questiongroup,
            how_marked__in=self.how_marked_in,
            previous_question__isnull=False,
        ).exists()

        if is_previous:
            self.has_previous_questions = True
            audit_rt = ResponseType.objects.get(type="Audit")
            question_list = self.questions.values_list(
                "previous_question_id", flat=True
            )
            prev_responses = Response.objects.filter(
                authority=self.authority,
                question__in=question_list,
                response_type=audit_rt,
            ).select_related("question")

            response_map = {}
            for r in prev_responses:
                response_map[r.question.id] = r

            for q in self.questions:
                data = initial[q.id]
                data["previous_response"] = response_map.get(q.previous_question_id)

                initial[q.id] = data

        return initial

    def process_form(self, form):
        cleaned_data = form.cleaned_data
        if (
            cleaned_data.get("option", None) is not None
            or len(list(cleaned_data.get("multi_option", None))) > 0
        ):
            form.instance.response_type = self.rt
            form.instance.user = self.request.user
            form.save()
            logger.debug(f"saved form {form.prefix}")
        else:
            logger.debug(f"did not save form {form.prefix}")
            logger.debug(
                f"option is {cleaned_data.get('option', None)}, multi is {cleaned_data.get('multi_option', None)}"
            )


class AuthoritySectionJSONQuestion(BaseResponseJSONView):
    pass
