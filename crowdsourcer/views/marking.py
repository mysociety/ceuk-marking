import logging

from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.generic import FormView, ListView, TemplateView

from crowdsourcer.forms import SessionPropertyForm
from crowdsourcer.marking import get_assignment_progress, get_cached_assignment_progress
from crowdsourcer.models import (
    Assigned,
    MarkingSession,
    PublicAuthority,
    ResponseType,
    SessionProperties,
    SessionPropertyValues,
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
                session = sessions.first()
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
                            user=user, marking_session=session
                        ).first()
                        if self.request.current_session != session:
                            url = reverse(
                                "session_urls:authority_ror_sections",
                                kwargs={
                                    "name": assignment.authority.name,
                                    "marking_session": session,
                                },
                            )
                        else:
                            url = reverse(
                                "authority_ror_sections",
                                kwargs={
                                    "name": assignment.authority.name,
                                },
                            )
                    # if they have nothing assigned then it's fine to show then the blank
                    # no assignments screen so handle everything else
                    else:
                        if self.request.current_session != session:
                            url = reverse(
                                "session_urls:authority_ror_authorities",
                                kwargs={
                                    "marking_session": session,
                                },
                            )
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

        progress = None
        if user.has_perm("crowdsourcer.can_view_all_responses"):
            if hasattr(user, "marker"):
                m = user.marker
                response_type = m.response_type.type
            else:
                response_type = self.request.current_stage.type
            progress = get_cached_assignment_progress(
                f"{self.request.current_session.label} {response_type}"
            )

        if progress is None:
            progress = get_assignment_progress(
                context["assignments"],
                self.request.current_session.label,
                self.request.current_stage.type,
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
        initial = super().get_initial_obj()

        if self.has_previous():
            audit_rt = ResponseType.objects.get(type="Audit")
            initial = self.add_previous(initial, audit_rt)

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


class SectionPropertiesView(FormView):
    template_name = "crowdsourcer/authority_properties.html"
    form = SessionPropertyForm

    def check_permissions(self):
        denied = True
        user = self.request.user

        if user.is_superuser:
            return True

        if user.is_anonymous:
            raise PermissionDenied

        if not user.marker.marking_session.filter(
            pk=self.request.current_session.pk
        ).exists():
            raise PermissionDenied

        stage = get_object_or_404(ResponseType, type=self.kwargs["stage"])
        authority = get_object_or_404(PublicAuthority, name=self.kwargs["name"])

        if (
            user.marker.response_type == stage
            and Assigned.objects.filter(
                user=user,
                response_type=stage,
                marking_session=self.request.current_session,
                authority=authority,
            ).exists()
        ):
            denied = False
        elif (
            stage.type == "Right of Reply"
            and user.marker.response_type == stage
            and user.marker.authority == authority
        ):
            denied = False

        if denied:
            raise PermissionDenied

    def get_initial(self):
        kwargs = super().get_initial()
        stage = ResponseType.objects.get(type=self.kwargs["stage"])
        authority = PublicAuthority.objects.get(name=self.kwargs["name"])

        properties = SessionProperties.objects.filter(
            marking_session=self.request.current_session,
            stage=stage,
            active=True,
        )
        if not properties.exists():
            raise Http404

        properties = SessionPropertyValues.objects.filter(
            property__in=properties,
            authority=authority,
        ).select_related("property")

        for prop in properties:
            kwargs[prop.property.name] = prop.value

        return kwargs

    def get_form(self):
        self.check_permissions()

        stage = self.kwargs["stage"]
        properties = SessionProperties.objects.filter(
            marking_session=self.request.current_session,
            stage__type=stage,
            active=True,
        ).order_by("order")

        self.properties = properties

        form = self.form(properties=properties, **self.get_form_kwargs())

        return form

    def get_context_data(self, **kwargs):
        context_data = super().get_context_data(**kwargs)

        stage = self.kwargs["stage"]
        name = self.kwargs["name"]
        url_kwargs = {
            "marking_session": self.request.current_session.label,
            "name": name,
        }

        back_link = reverse(
            "session_urls:home",
            kwargs={"marking_session": self.request.current_session},
        )

        if stage == "Right of Reply":
            back_link = reverse(
                "session_urls:authority_ror_sections", kwargs=url_kwargs
            )

        context_data["back_link"] = back_link
        return context_data

    def form_valid(self, form):
        authority = PublicAuthority.objects.get(name=self.kwargs["name"])

        cleaned_data = form.cleaned_data

        for prop in self.properties:
            if cleaned_data.get(prop.name):
                SessionPropertyValues.objects.update_or_create(
                    authority=authority,
                    property=prop,
                    defaults={"value": cleaned_data[prop.name]},
                )

        context = self.get_context_data()
        context["message"] = "Your answers have been saved."
        return self.render_to_response(context)

    def get_success_url(self):
        stage = ResponseType.objects.get(type=self.kwargs["stage"])
        authority = PublicAuthority.objects.get(name=self.kwargs["authority"])
        return reverse(
            "session_urls:authority_properties",
            kwargs={
                "marking_session": self.request.current_session.label,
                "stage": stage.type,
                "authority": authority.name,
            },
        )
