import logging

from django.contrib.auth.mixins import UserPassesTestMixin
from django.contrib.auth.models import User
from django.db.models import Count, OuterRef, Subquery
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.views.generic import FormView, ListView

from crowdsourcer.forms import (
    MarkerFormset,
    UserForm,
    VolunteerAssignmentFormset,
    VolunteerBulkAssignForm,
)
from crowdsourcer.models import (
    Assigned,
    Marker,
    MarkingSession,
    PublicAuthority,
    ResponseType,
    Section,
)

logger = logging.getLogger(__name__)


class VolunteerAccessMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.has_perm("crowdsourcer.can_manage_users")


class VolunteersView(VolunteerAccessMixin, ListView):
    template_name = "crowdsourcer/volunteers/list.html"
    context_object_name = "volunteers"

    def get_queryset(self):
        return (
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
            .order_by("username")
        )


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

        formset = MarkerFormset(
            instance=self.user,
            form_kwargs={"session": self.request.current_session},
            **self.get_form_kwargs()
        )

        context["formset"] = formset

        return context

    def form_valid(self, form):
        context = self.get_context_data()
        formset = context["formset"]

        if formset.is_valid():
            form.save()
            formset.save()

            return super().form_valid(form)


class VolunteerAssignentView(VolunteerAccessMixin, FormView):
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
        return PublicAuthority.objects.filter(
            marking_session=marking_session,
            questiongroup__marking_session=marking_session,
        ).exclude(
            id__in=Assigned.objects.filter(
                response_type=self.request.GET["rt"],
                marking_session=self.request.GET["ms"],
                section=self.request.GET["s"],
            ).values_list("authority_id", flat=True)
        )

    def render_to_response(self, context, **response_kwargs):
        data = []

        for a in context["authorities"]:
            data.append({"name": a.name, "id": a.id})

        return JsonResponse({"results": data})


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

            m, c = Marker.objects.update_or_create(user=u, response_type=rt)
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
