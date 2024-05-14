import logging

from django.contrib.auth.mixins import UserPassesTestMixin
from django.contrib.auth.models import User
from django.db.models import Count, OuterRef, Subquery
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.views.generic import FormView, ListView

from crowdsourcer.forms import MarkerFormset, UserForm, VolunteerAssignmentFormset
from crowdsourcer.models import Assigned

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

        context["formset"] = formset

        return context

    def form_valid(self, form):
        if form.is_valid():
            form.save()

            return super().form_valid(form)

    def form_invalid(self, form):
        print(form.errors)
        return super().form_invalid(form)
