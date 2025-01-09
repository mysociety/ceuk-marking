import re

from django.contrib import messages
from django.contrib.auth.mixins import UserPassesTestMixin
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.views.generic import FormView, ListView

import pandas as pd

from crowdsourcer.forms import OptionFormset, QuestionBulkUploadForm, QuestionFormset
from crowdsourcer.models import (
    Option,
    PublicAuthority,
    Question,
    Response,
    ResponseType,
    Section,
)


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
                "section_name": self.kwargs["section_name"],
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


class WeightingsView(UserPassesTestMixin, FormView):
    template_name = "crowdsourcer/questions/weightings.html"
    form_class = QuestionFormset

    def test_func(self):
        return self.request.user.has_perm("crowdsourcer.can_manage_users")

    def get_success_url(self):
        return reverse(
            "session_urls:edit_weightings",
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

        questions = Question.objects.filter(
            section=self.section,
        ).order_by("number", "number_part")
        return self.form_class(queryset=questions, **self.get_form_kwargs())

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["section"] = self.section

        return context

    def form_valid(self, form):
        form.save()
        return super().form_valid(form)


class QuestionListView(UserPassesTestMixin, ListView):
    template_name = "crowdsourcer/questions/question_list.html"
    context_object_name = "questions"

    def test_func(self):
        return self.request.user.has_perm("crowdsourcer.can_manage_users")

    def get_queryset(self):
        return Question.objects.filter(
            section__title=self.kwargs["section_name"],
            section__marking_session=self.request.current_session,
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["section"] = get_object_or_404(
            Section,
            title=self.kwargs["section_name"],
            marking_session=self.request.current_session,
        )

        return context


class QuestionBulkUpdateView(UserPassesTestMixin, FormView):
    template_name = "crowdsourcer/questions/question_bulk_upload.html"
    form_class = QuestionBulkUploadForm

    def test_func(self):
        return self.request.user.has_perm("crowdsourcer.can_manage_users")

    def get_success_url(self):
        return reverse(
            "session_urls:question_bulk_update",
            kwargs={
                "marking_session": self.request.current_session.label,
                "section_name": self.kwargs["section_name"],
                "question": self.kwargs["question"],
            },
        )

    def get_form(self):
        self.section = get_object_or_404(
            Section,
            title=self.kwargs["section_name"],
            marking_session=self.request.current_session,
        )

        q_parts = re.match(r"(\d+)([a-z]?)", self.kwargs["question"])
        q_kwargs = {
            "section": self.section,
            "number": q_parts.groups()[0],
        }

        if len(q_parts.groups()) == 2 and q_parts.groups()[1] != "":
            q_kwargs["number_part"] = q_parts.groups()[1]

        self.question = get_object_or_404(Question, **q_kwargs)
        return self.form_class(
            self.question.pk,
            [(rt.type, rt.type) for rt in ResponseType.objects.all()],
            self.request.current_session,
            **self.get_form_kwargs(),
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["section"] = self.section
        context["question"] = self.question
        context["success"] = self.request.GET.get("success")

        return context

    def form_valid(self, form):
        data = form.cleaned_data

        question = get_object_or_404(Question, id=data["question"])
        stage = get_object_or_404(ResponseType, type=data["stage"])
        is_multi = question.question_type == "multiple_choice"

        counts = {"updated": 0, "added": 0, "deleted": 0}
        with transaction.atomic():
            for index, row in form.responses_df.iterrows():
                answer = row["answer"].strip()
                authority = PublicAuthority.objects.get(
                    name=row["authority"],
                    marking_session=self.request.current_session,
                )

                if answer != "-":
                    if is_multi:
                        answers = answer.split("|")

                    if not is_multi:
                        option = Option.objects.get(
                            question=question, description=answer
                        )

                try:
                    response = Response.objects.get(
                        question=question, response_type=stage, authority=authority
                    )
                    if answer == "-":
                        response.delete()
                        counts["deleted"] += 1
                    else:
                        changed = False
                        opts = {}
                        for col in [
                            "page_number",
                            "evidence",
                            "public_notes",
                            "private_notes",
                        ]:
                            val = row[col]
                            if pd.isna(val):
                                val = None
                                if col == "private_notes":
                                    val = ""
                            if val != getattr(response, col):
                                opts[col] = val
                                changed = True
                        if not is_multi and response.option != option:
                            changed = True
                            opts["option"] = option

                        if changed:
                            counts["updated"] += 1
                            response.user = self.request.user
                            for k, v in opts.items():
                                setattr(response, k, v)
                            response.save()

                            if is_multi:
                                response.multi_option.clear()
                                for a in answers:
                                    option = Option.objects.get(
                                        question=question, description=a
                                    )
                                    response.multi_option.add(option.id)

                except Response.DoesNotExist:
                    if answer != "-":
                        counts["added"] += 1
                        opts = {
                            "question": question,
                            "response_type": stage,
                            "authority": authority,
                            "user": self.request.user,
                        }
                        for col in ["page_number", "evidence", "public_notes"]:
                            if pd.isna(row[col]) is False:
                                opts[col] = row[col]
                        if not is_multi:
                            opts["option"] = option

                        response = Response.objects.create(**opts)

                        if is_multi:
                            for a in answers:
                                option = Option.objects.get(
                                    question=question, description=a
                                )
                                response.multi_option.add(option.id)

        messages.add_message(self.request, messages.SUCCESS, "Question updated!")
        messages.add_message(
            self.request,
            messages.INFO,
            f"{counts['updated']} updated, {counts['added']} added, {counts['deleted']} deleted",
        )
        return super().form_valid(form)
