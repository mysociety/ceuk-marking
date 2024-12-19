from django.contrib.auth.mixins import UserPassesTestMixin
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.views.generic import FormView, ListView

from crowdsourcer.forms import OptionFormset
from crowdsourcer.models import Option, Section


class SectionList(ListView):
    template_name = "crowdsourcer/questions/sections.html"
    context_object_name = "sections"

    def get_queryset(self):
        return Section.objects.filter(marking_session=self.request.current_session)


class OptionsView(UserPassesTestMixin, FormView):
    template_name = "crowdsourcer/questions/options.html"
    form_class = OptionFormset

    def test_func(self):
        return self.request.user.has_perm("crowdsourcer.can_manage_users")

    def get_success_url(self):
        return reverse(
            "session_urls:edit_options",
            kwargs={
                "marking_session": self.request.current_session.label,
                "section_name": "Buildings & Heating",
            },
        )

    def get_form(self):
        self.section = get_object_or_404(
            Section,
            title=self.kwargs["section_name"],
            marking_session=self.request.current_session,
        )

        options = (
            Option.objects.filter(
                question__section=self.section,
            )
            .order_by("question__number", "question__number_part", "ordering")
            .select_related("question")
        )
        return self.form_class(queryset=options, **self.get_form_kwargs())

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["section"] = self.section

        return context

    def form_valid(self, form):
        form.save()
        return super().form_valid(form)
