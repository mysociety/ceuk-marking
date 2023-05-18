import csv
import logging
import re
from collections import defaultdict

from django.contrib.auth.mixins import UserPassesTestMixin
from django.db.models import Count
from django.http import HttpResponse
from django.utils.text import slugify
from django.views.generic import ListView

from crowdsourcer.models import PublicAuthority, Question, Response

logger = logging.getLogger(__name__)


class AllMarksBaseCSVView(UserPassesTestMixin, ListView):
    context_object_name = "responses"
    response_type = "First Mark"
    file_name = "grace_first_mark_scores.csv"

    def test_func(self):
        return self.request.user.is_superuser

    def get_queryset(self):
        return (
            Response.objects.filter(response_type__type=self.response_type)
            .select_related("question", "authority", "question__section", "option")
            .order_by(
                "authority",
                "question__section__title",
                "question__number",
                "question__number_part",
            )
            .annotate(multi_count=Count("multi_option__pk"))
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        responses = defaultdict(dict)
        questions = (
            Question.objects.select_related("section")
            .all()
            .order_by("section__title", "number", "number_part")
        )

        headers = {}
        for q in questions:
            q_desc = f"{q.section.title}: {q.number_and_part}"
            headers[q_desc] = 1

        for response in context["responses"]:
            score = 0

            if response.multi_count > 0:
                for opt in response.multi_option.all():
                    score += opt.score
            elif response.option is not None:
                score = response.option.score
            else:
                score = "-"

            q = response.question
            q_desc = f"{q.section.title}: {q.number_and_part}"

            responses[response.authority.name][q_desc] = score

        context["headers"] = sorted(headers.keys())
        context["marks"] = responses

        return context

    def render_to_response(self, context, **response_kwargs):
        response = HttpResponse(
            content_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{self.file_name}"'},
        )
        writer = csv.writer(response)
        headers = [
            "authority",
        ] + context["headers"]
        writer.writerow(headers)
        for authority, mark in context["marks"].items():
            row = [authority] + [mark.get(q, "-") for q in context["headers"]]
            writer.writerow(row)
        return response


class AllFirstMarksCSVView(AllMarksBaseCSVView):
    pass


class AllAuditMarksCSVView(AllMarksBaseCSVView):
    response_type = "Audit"
    file_name = "grace_audit_mark_scores.csv"


class CouncilDisagreeMarkCSVView(AllMarksBaseCSVView):
    context_object_name = "responses"
    response_type = "First Mark"
    ror_response_type = "Right of Reply"
    file_name = "grace_council_disagree_scores.csv"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        council_responses = (
            Response.objects.filter(response_type__type=self.ror_response_type)
            .select_related("question", "authority", "question__section", "option")
            .order_by(
                "authority",
                "question__section__title",
                "question__number",
                "question__number_part",
            )
            .annotate(multi_count=Count("multi_option__pk"))
        )

        disagree = defaultdict(dict)
        marks = context["marks"]

        for response in council_responses:
            q = response.question
            q_desc = f"{q.section.title}: {q.number_and_part}"

            disagree[response.authority.name][q_desc] = ""
            if not response.agree_with_response:
                mark = marks[response.authority.name].get(q_desc, None)
                if mark is not None and mark != "-" and mark > 0:
                    disagree[response.authority.name][q_desc] = "Y"

        context["marks"] = disagree
        return context


class SelectQuestionView(UserPassesTestMixin, ListView):
    template_name = "crowdsourcer/stats_select_question.html"
    context_object_name = "questions"

    def test_func(self):
        return self.request.user.is_superuser

    def get_queryset(self):
        return Question.objects.select_related("section").order_by(
            "section__title", "number", "number_part"
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        sections = defaultdict(list)

        for q in context["questions"]:
            sections[q.section.title].append(q)

        # items does not work on defaultdicts in a template :|
        context["sections"] = dict(sections)

        return context


class QuestionDataCSVView(UserPassesTestMixin, ListView):
    context_object_name = "responses"
    response_type = "First Mark"

    def test_func(self):
        return self.request.user.is_superuser

    def get_queryset(self):
        stage = self.kwargs["stage"]
        section = self.kwargs["section"]
        q = self.kwargs["question"]

        if stage == "audit":
            self.response_type = "Audit"

        q_number, q_part = re.search(r"(\d+)(\w*)", q).groups()
        responses = (
            Response.objects.filter(
                question__section__title=section,
                question__number=q_number,
                response_type__type=self.response_type,
            )
            .annotate(multi_count=Count("multi_option__pk"))
            .select_related("authority", "option")
            .order_by("authority")
        )

        if q_part is not None and q_part != "":
            responses = responses.filter(question__number_part=q_part)

        return responses

    def get_context_data(self, **kwargs):
        stage = self.kwargs["stage"]
        context = super().get_context_data(**kwargs)

        answers = {}

        for response in context["responses"]:
            score = 0
            answer = ""

            if response.multi_count > 0:
                descs = []
                for opt in response.multi_option.all():
                    descs.append(opt.description)
                    score += opt.score
                answer = ",".join(descs)
            elif response.option is not None:
                score = response.option.score
                answer = response.option.description
            else:
                score = "-"

            data = [
                response.authority.name,
                answer,
                score,
                response.public_notes,
                response.private_notes,
                response.page_number,
                response.evidence,
            ]

            answers[response.authority.name] = data

        authorities = []
        for authority in PublicAuthority.objects.all().order_by("name"):
            if answers.get(authority.name, None) is not None:
                authorities.append(answers[authority.name])
            else:
                authorities.append([authority.name, "-", "-", "-", "-", "-", "-"])

        section = self.kwargs["section"]
        q = self.kwargs["question"]

        context["file_prefix"] = f"{slugify(stage)}_data"
        context["file_postfix"] = f"{slugify(section)}_{q}"
        context["answers"] = authorities
        return context

    def render_to_response(self, context, **response_kwargs):
        file_name = f"{context['file_prefix']}_{context['file_postfix']}"
        response = HttpResponse(
            content_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{file_name}"'},
        )
        writer = csv.writer(response)
        headers = [
            "authority",
            "answer",
            "score",
            "public_notes",
            "private_notes",
            "page_number",
            "evidence",
        ]
        writer.writerow(headers)
        for answer in context["answers"]:
            writer.writerow(answer)
        return response
