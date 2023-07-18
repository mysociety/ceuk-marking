import csv
import logging
import re
from collections import defaultdict

from django.contrib.auth.mixins import UserPassesTestMixin
from django.db.models import Count
from django.http import HttpResponse
from django.utils.text import slugify
from django.views.generic import ListView, TemplateView

from crowdsourcer.models import PublicAuthority, Question, Response
from crowdsourcer.scoring import (
    calculate_council_totals,
    get_section_maxes,
    get_section_scores,
)

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

    def get_response_score(self, response):
        score = 0

        if response.multi_count > 0:
            for opt in response.multi_option.all():
                score += opt.score
        elif response.option is not None:
            score = response.option.score
        else:
            score = "-"

        return score

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
            score = self.get_response_score(response)

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


class AllRoRMarksCSVView(AllMarksBaseCSVView):
    response_type = "Right of Reply"
    file_name = "grace_ror_mark_scores.csv"

    def get_response_score(self, response):
        score = "-"

        if response.agree_with_response:
            score = "Yes"
        elif (
            response.agree_with_response is not None
            and not response.agree_with_response
        ):
            score = "No"

        return score


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
    headers = [
        "authority",
        "answer",
        "score",
        "public_notes",
        "private_notes",
        "page_number",
        "evidence",
    ]

    def test_func(self):
        return self.request.user.is_superuser

    def set_stage(self):
        stage = self.kwargs["stage"]
        if stage == "audit":
            self.response_type = "Audit"

    def get_queryset(self):
        self.set_stage()

        section = self.kwargs["section"]
        q = self.kwargs["question"]

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

    def blank_row(self, authority):
        return [authority, "-", "-", "-", "-", "-", "-"]

    def get_response_data(self, response):
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

        return data

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        answers = {}

        for response in context["responses"]:
            data = self.get_response_data(response)
            answers[response.authority.name] = data

        authorities = []
        for authority in PublicAuthority.objects.all().order_by("name"):
            if answers.get(authority.name, None) is not None:
                authorities.append(answers[authority.name])
            else:
                authorities.append(self.blank_row(authority.name))

        section = self.kwargs["section"]
        q = self.kwargs["question"]

        context["file_prefix"] = f"{slugify(self.response_type)}_data"
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
        writer.writerow(self.headers)
        for answer in context["answers"]:
            writer.writerow(answer)
        return response


class RoRQuestionDataCSVView(QuestionDataCSVView):
    response_type = "Right of Reply"
    headers = [
        "authority",
        "agree",
        "notes",
        "evidence",
    ]

    def set_stage(self):
        pass

    def blank_row(self, authority):
        return [authority, "-", "-", "-"]

    def get_response_data(self, response):
        answer = ""

        if response.agree_with_response:
            answer = "Yes"
        elif (
            response.agree_with_response is not None
            and not response.agree_with_response
        ):
            answer = "No"

        data = [
            response.authority.name,
            answer,
            response.private_notes,
            response.evidence,
        ]

        return data


class WeightedScoresDataCSVView(UserPassesTestMixin, TemplateView):
    def test_func(self):
        return self.request.user.is_superuser

    def get_context_data(self, **kwargs):
        ordered_sections = [
            "Buildings & Heating",
            "Transport",
            "Planning & Land Use",
            "Governance & Finance",
            "Biodiversity",
            "Collaboration & Engagement",
            "Waste Reduction & Food",
            "Transport (CA)",
            "Buildings, Heating & Green Skills (CA)",
            "Governance & Finance (CA)",
            "Planning, Biodiversity & Land Use (CA)",
            "Collaboration & Engagement (CA)",
        ]
        context = super().get_context_data(**kwargs)

        council_gss_map, groups = PublicAuthority.maps()
        maxes, group_maxes, q_maxes, weighted_maxes = get_section_maxes()
        raw_scores, weighted = get_section_scores(q_maxes)

        council_totals, section_totals = calculate_council_totals(
            raw_scores, weighted, weighted_maxes, maxes, group_maxes, groups
        )

        rows = []
        rows.append(
            [
                "council",
            ]
            + ordered_sections
            + [
                "total",
            ]
        )

        for council, council_score in section_totals.items():
            row = [council]
            for section in ordered_sections:
                if council_score.get(section, None) is not None:
                    row.append(council_score[section]["weighted"])
                else:
                    row.append(0)

            row.append(council_totals[council]["weighted_total"])

            rows.append(row)

        context["weighted_scores"] = rows

        return context

    def render_to_response(self, context, **response_kwargs):
        file_name = "all_sections_scores.csv"

        response = HttpResponse(
            content_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{file_name}"'},
        )
        writer = csv.writer(response)
        for row in context["weighted_scores"]:
            writer.writerow(row)
        return response
