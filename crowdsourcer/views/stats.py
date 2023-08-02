import csv
import logging
import re
from collections import defaultdict

from django.contrib.auth.mixins import UserPassesTestMixin
from django.db.models import Count
from django.http import HttpResponse
from django.utils.text import slugify
from django.views.generic import ListView, TemplateView

from crowdsourcer.models import Option, PublicAuthority, Question, Response
from crowdsourcer.scoring import (
    get_duplicate_responses,
    get_exact_duplicates,
    get_scoring_object,
    get_section_maxes,
    weighting_to_points,
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


class BaseScoresView(UserPassesTestMixin, TemplateView):
    def test_func(self):
        return self.request.user.is_superuser

    def get_scores(self):
        self.scoring = get_scoring_object()

    def render_to_response(self, context, **response_kwargs):
        response = HttpResponse(
            content_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{self.file_name}"'},
        )
        writer = csv.writer(response)
        for row in context["rows"]:
            writer.writerow(row)
        return response


class WeightedScoresDataCSVView(BaseScoresView):
    file_name = "all_sections_scores.csv"

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
            "Buildings & Heating & Green Skills (CA)",
            "Governance & Finance (CA)",
            "Planning & Biodiversity (CA)",
            "Collaboration & Engagement (CA)",
        ]
        context = super().get_context_data(**kwargs)

        self.get_scores()

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

        for council, council_score in self.scoring["section_totals"].items():
            row = [council]
            for section in ordered_sections:
                if council_score.get(section, None) is not None:
                    row.append(council_score[section]["weighted"])
                else:
                    row.append(0)

            row.append(self.scoring["council_totals"][council]["weighted_total"])

            rows.append(row)

        context["rows"] = rows

        return context


class SectionScoresDataCSVView(BaseScoresView):
    file_name = "raw_and_weighted_sections_scores.csv"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        self.get_scores()

        rows = []
        rows.append(
            [
                "council",
                "section",
                "raw score",
                "raw max",
                "raw weighted",
                "weighted max",
                "weighted score",
                "section weighted score",
            ]
        )

        for council, council_score in self.scoring["section_totals"].items():
            for section, scores in council_score.items():
                row = [
                    council,
                    section,
                    scores["raw"],
                    self.scoring["council_maxes"][council]["raw"][section][
                        self.scoring["council_groups"][council]
                    ],
                    scores["raw_weighted"],
                    self.scoring["council_maxes"][council]["weighted"][section][
                        self.scoring["council_groups"][council]
                    ],
                    scores["unweighted_percentage"],
                    scores["weighted"],
                ]

                rows.append(row)

        context["rows"] = rows

        return context


class QuestionScoresCSV(UserPassesTestMixin, ListView):
    context_object_name = "options"

    def test_func(self):

        return self.request.user.is_superuser

    def get_queryset(self):
        return Option.objects.select_related("question", "question__section").order_by(
            "question__section__title",
            "question__number",
            "question__number_part",
            "score",
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        scoring = {}
        get_section_maxes(scoring)

        sections = defaultdict(dict)
        for option in context["options"]:
            section = option.question.section.title
            number = option.question.number_and_part

            option_text = f"{option.description} ({option.score})"

            try:
                q = sections[section][number]
            except KeyError:
                max_score = scoring["q_maxes"][section].get(number, 0)
                q = {
                    "q": option.question.description,
                    "how_marked": option.question.how_marked,
                    "type": option.question.question_type,
                    "raw_max": max_score,
                    "weighted_max": weighting_to_points(option.question.weighting),
                    "options": [],
                }
            q["options"].append(option_text)

            sections[section][number] = q

        rows = []
        rows.append(
            [
                "section",
                "No",
                "question",
                "how marked",
                "type",
                "raw max",
                "weighted max",
                "options",
            ]
        )

        for section, questions in sections.items():
            keys = sorted(
                list(questions.keys()),
                key=lambda s: [
                    int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", s)
                ],
            )
            for k in keys:
                q = questions[k]
                row = [
                    section,
                    k,
                    q["q"],
                    q["how_marked"],
                    q["type"],
                    q["raw_max"],
                    q["weighted_max"],
                    q["options"],
                ]
                rows.append(row)

        context["rows"] = rows

        return context

    def render_to_response(self, context, **response_kwargs):
        response = HttpResponse(
            content_type="text/csv",
            headers={
                "Content-Disposition": 'attachment; filename="questions_with_max_scores.csv"'
            },
        )
        writer = csv.writer(response)
        for row in context["rows"]:
            writer.writerow(row)
        return response


class BadResponsesView(UserPassesTestMixin, ListView):
    context_object_name = "responses"
    template_name = "crowdsourcer/bad_responses.html"

    def test_func(self):
        return self.request.user.is_superuser

    def get_queryset(self):
        responses = (
            Response.objects.filter(
                response_type__type="Audit",
                option__isnull=True,
                multi_option__isnull=True,
            )
            .select_related("authority", "question", "question__section")
            .order_by("authority", "question__section")
        )

        return responses


class DuplicateResponsesView(UserPassesTestMixin, ListView):
    context_object_name = "responses"
    template_name = "crowdsourcer/duplicate_responses.html"

    def test_func(self):
        return self.request.user.is_superuser

    def get_queryset(self):
        return get_duplicate_responses()

    def get_context_data(self, **kwargs):
        ignore_exacts = self.request.GET.get("ignore_exacts", 0)
        context = super().get_context_data(**kwargs)

        duplicates = context["responses"]

        exact_duplicates = get_exact_duplicates(duplicates)

        exact_ids = []
        for exact in exact_duplicates:
            exact_ids.append(f"{exact[0].question_id}:{exact[0].authority_id}")

        dupes = []
        for d in duplicates:
            exact_id = f"{d['question_id']}:{d['authority_id']}"

            if ignore_exacts == "1" and exact_id in exact_ids:
                continue

            rs = Response.objects.filter(
                question_id=d["question_id"],
                authority_id=d["authority_id"],
                response_type__type="Audit",
            ).select_related("authority", "question", "question__section")

            dupe = []
            for r in rs:
                r.dupe_id = f"{r.question_id}:{r.authority_id}"
                dupe.append(r)
            dupes.append(dupe)

        context["ignore_exacts"] = ignore_exacts
        context["exact_dupes"] = exact_ids
        context["dupes"] = dupes

        return context
