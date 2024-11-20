import logging

from django.contrib.auth.mixins import UserPassesTestMixin
from django.contrib.auth.models import User
from django.contrib.postgres.aggregates import StringAgg
from django.db.models import Count, OuterRef, Subquery
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.views.generic import FormView, ListView

from django_filters.views import FilterView

from crowdsourcer.filters import VolunteerFilter
from crowdsourcer.forms import (
    CreateMarkerForm,
    MarkerFormset,
    ResetEmailForm,
    UserForm,
    VolunteerAssignmentFormset,
    VolunteerBulkAssignForm,
    VolunteerDeactivateForm,
)
from crowdsourcer.models import (
    Assigned,
    Marker,
    MarkingSession,
    PublicAuthority,
    ResponseType,
    Section,
)
from crowdsourcer.volunteers import deactivate_stage_volunteers, send_registration_email

logger = logging.getLogger(__name__)


class VolunteerAccessMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.has_perm("crowdsourcer.can_manage_users")


class VolunteersView(VolunteerAccessMixin, FilterView):
    template_name = "crowdsourcer/volunteers/list.html"
    context_object_name = "volunteers"
    filterset_class = VolunteerFilter

    def get_filterset(self, filterset_class):
        fs = super().get_filterset(filterset_class)

        fs.filters["assigned_section"].field.choices = Section.objects.filter(
            marking_session=self.request.current_session
        ).values_list("title", "title")
        return fs

    def get_queryset(self):
        qs = (
            User.objects.filter(marker__marking_session=self.request.current_session)
            .select_related("marker")
            .annotate(
                num_assignments=Subquery(
                    Assigned.objects.filter(
                        marking_session=self.request.current_session,
                        user=OuterRef("pk"),
                    )
                    .values("user_id")
                    .annotate(num_assignments=Count("pk"))
                    .values("num_assignments")
                )
            )
            .annotate(
                assigned_section=(
                    Subquery(
                        Assigned.objects.filter(
                            marking_session=self.request.current_session,
                            user=OuterRef("pk"),
                        )
                        .values_list("user")
                        .annotate(
                            joined_title=StringAgg(
                                "section__title", distinct=True, delimiter=", "
                            )
                        )
                        .values("joined_title")
                    )
                )
            )
            .order_by("username")
        )

        return qs


class VolunteerAddView(VolunteerAccessMixin, FormView):
    template_name = "crowdsourcer/volunteers/create.html"
    form_class = UserForm
    context_object_name = "volunteer"

    def get_success_url(self):
        return reverse(
            "session_urls:list_volunteers",
            kwargs={"marking_session": self.request.current_session.label},
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        marker_form = CreateMarkerForm(
            **{**self.get_form_kwargs(), "session": self.request.current_session}
        )

        context["marker_form"] = marker_form

        return context

    def form_valid(self, form):
        context = self.get_context_data()
        marker_form = context["marker_form"]

        if marker_form.is_valid():
            u = form.save()
            marker_form.instance.user_id = u.id
            m = marker_form.save()

            m.marking_session.add(self.request.current_session)

            if marker_form.cleaned_data["send_reset"] is True:
                send_registration_email(u, self.request.get_host())

            return super().form_valid(form)


class VolunteerEditView(VolunteerAccessMixin, FormView):
    template_name = "crowdsourcer/volunteers/edit.html"
    form_class = UserForm
    context_object_name = "volunteer"

    def get_success_url(self):
        return reverse(
            "session_urls:list_volunteers",
            kwargs={"marking_session": self.request.current_session.label},
        )

    def get_form(self, form_class=None):
        if form_class is None:
            form_class = self.form_class

        user = get_object_or_404(
            User,
            pk=self.kwargs["pk"],
            marker__marking_session=self.request.current_session,
        )
        self.user = user

        return form_class(instance=user, **self.get_form_kwargs())

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        reset_form = ResetEmailForm(initial={"user_id": self.user.id})

        formset = MarkerFormset(
            instance=self.user,
            form_kwargs={"session": self.request.current_session},
            **self.get_form_kwargs()
        )

        context["formset"] = formset
        context["reset_form"] = reset_form
        context["user"] = self.user

        return context

    def form_valid(self, form):
        context = self.get_context_data()
        formset = context["formset"]

        if formset.is_valid():
            form.save()
            formset.save()

            return super().form_valid(form)


class VolunteerSendResetEmailView(VolunteerAccessMixin, FormView):
    form_class = ResetEmailForm
    template_name = "crowdsourcer/volunteers/edit.html"

    def get_success_url(self):
        return reverse(
            "session_urls:list_volunteers",
            kwargs={"marking_session": self.request.current_session.label},
        )

    def form_valid(self, form):
        if form.is_valid():
            user_id = form.cleaned_data["user_id"]
            user = get_object_or_404(User, pk=user_id)
            send_registration_email(user, self.request.get_host())

            return super().form_valid(form)


class VolunteerAssignmentView(VolunteerAccessMixin, FormView):
    template_name = "crowdsourcer/volunteers/assign.html"
    form_class = VolunteerAssignmentFormset

    def get_success_url(self):
        return reverse(
            "session_urls:list_volunteers",
            kwargs={"marking_session": self.request.current_session.label},
        )

    def get_form(self, form_class=None):
        if form_class is None:
            form_class = self.form_class

        user = get_object_or_404(
            User,
            pk=self.kwargs["user_id"],
            marker__marking_session=self.request.current_session,
        )
        self.user = user

        return form_class(instance=user, **self.get_form_kwargs())

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        formset = VolunteerAssignmentFormset(
            instance=self.user,
            form_kwargs={"session": self.request.current_session},
            **self.get_form_kwargs()
        )

        context["user"] = self.user
        context["formset"] = formset

        return context

    def form_valid(self, form):
        if form.is_valid():
            form.save()

            return super().form_valid(form)

    def form_invalid(self, form):
        print(form.errors)
        return super().form_invalid(form)


class AvailableAssignmentAuthorities(VolunteerAccessMixin, ListView):
    context_object_name = "authorities"

    def get_queryset(self):
        if (
            self.request.GET.get("ms") is None
            or self.request.GET.get("rt") is None
            or self.request.GET.get("s") is None
        ):
            return []

        marking_session = MarkingSession.objects.get(id=self.request.GET["ms"])
        exclusions = Assigned.objects.filter(
            response_type=self.request.GET["rt"],
            marking_session=self.request.GET["ms"],
            section=self.request.GET["s"],
            authority__isnull=False,
        )
        # we want to be able to re-select the authority that was already assigned
        # for existing assignments
        if self.request.GET.get("id") is not None:
            id = int(self.request.GET["id"])
            if id:
                exclusions = exclusions.exclude(id=id)

        exclusions = exclusions.values_list("authority_id", flat=True)
        return (
            PublicAuthority.objects.filter(
                marking_session=marking_session,
                questiongroup__marking_session=marking_session,
            )
            .exclude(id__in=exclusions)
            .order_by("name")
        )

    def render_to_response(self, context, **response_kwargs):
        data = []

        for a in context["authorities"]:
            data.append({"name": a.name, "id": a.id})

        return JsonResponse({"results": data})


class DeactivateVolunteers(VolunteerAccessMixin, FormView):
    template_name = "crowdsourcer/volunteers/deactivate.html"
    form_class = VolunteerDeactivateForm

    def get_form(self, form_class=None):
        if form_class is None:
            form_class = self.form_class

        return form_class(
            [(rt.type, rt.type) for rt in ResponseType.objects.all()],
            **self.get_form_kwargs()
        )

    def get_success_url(self):
        return reverse(
            "session_urls:list_volunteers",
            kwargs={"marking_session": self.request.current_session.label},
        )

    def form_valid(self, form):
        ms = self.request.current_session
        rt = ResponseType.objects.get(type=form.cleaned_data.get("stage"))

        deactivate_stage_volunteers(rt, ms)
        return super().form_valid(form)


class BulkAssignVolunteer(VolunteerAccessMixin, FormView):
    template_name = "crowdsourcer/volunteers/bulk_assign.html"
    form_class = VolunteerBulkAssignForm

    def get_initial(self):
        kwargs = super().get_initial()
        kwargs["session"] = self.request.current_session.label
        return kwargs

    def get_form(self, form_class=None):
        if form_class is None:
            form_class = self.form_class

        return form_class(
            [(rt.type, rt.type) for rt in ResponseType.objects.all()],
            **self.get_form_kwargs()
        )

    def get_success_url(self):
        return reverse(
            "session_urls:list_volunteers",
            kwargs={"marking_session": self.request.current_session.label},
        )

    def form_valid(self, form):
        ms = self.request.current_session
        rt = ResponseType.objects.get(type=form.cleaned_data.get("response_type"))

        for _, row in form.volunteer_df.iterrows():
            u, c = User.objects.update_or_create(
                username=row["Email"],
                defaults={
                    "email": row["Email"],
                    "first_name": row["First Name"],
                    "last_name": row["Last Name"],
                },
            )
            u.save()

            m, c = Marker.objects.update_or_create(
                user=u, defaults={"response_type": rt, "send_welcome_email": True}
            )
            m.marking_session.add(ms)

            max_assignments = form.cleaned_data["num_assignments"]
            num_assignments = max_assignments
            existing_assignments = Assigned.objects.filter(
                user=u, marking_session=ms, response_type=rt
            ).count()

            if existing_assignments >= max_assignments:
                continue

            num_assignments = max_assignments - existing_assignments

            section = Section.objects.get(
                title=row["Assigned Section"], marking_session=ms
            )
            assigned = Assigned.objects.filter(
                marking_session=ms,
                section=section,
                response_type=rt,
            ).values("authority")

            to_assign = PublicAuthority.objects.filter(
                marking_session=ms, questiongroup__marking_session=ms
            ).exclude(id__in=assigned)[:num_assignments]

            for a in to_assign:
                a, c = Assigned.objects.update_or_create(
                    user=u,
                    marking_session=ms,
                    response_type=rt,
                    section=section,
                    authority=a,
                )

        return super().form_valid(form)
