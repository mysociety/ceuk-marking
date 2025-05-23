import csv
import logging
import re
from collections import defaultdict

from django.conf import settings
from django.contrib.auth.mixins import UserPassesTestMixin
from django.db.models import Count
from django.http import HttpResponse, JsonResponse
from django.utils.text import slugify
from django.views.generic import ListView, TemplateView

import pandas as pd
from django_filters.views import FilterView

from crowdsourcer.filters import ResponseFilter
from crowdsourcer.models import (
    MarkingSession,
    Option,
    PublicAuthority,
    Question,
    Response,
    ResponseType,
    Section,
    SessionConfig,
    SessionPropertyValues,
)
from crowdsourcer.scoring import (
    clear_exception_cache,
    get_all_question_data,
    get_duplicate_responses,
    get_exact_duplicates,
    get_response_data,
    get_scoring_object,
    get_section_maxes,
    weighting_to_points,
)

logger = logging.getLogger(__name__)


class StatsUserTestMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.has_perm("crowdsourcer.can_view_stats")


class StatsView(StatsUserTestMixin, TemplateView):
    template_name = "crowdsourcer/stats.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["page_title"] = "Stats"

        return context


class AllMarksBaseCSVView(StatsUserTestMixin, ListView):
    context_object_name = "responses"
    response_type = "First Mark"
    file_name = "grace_first_mark_scores.csv"

    def get_queryset(self):
        return (
            Response.objects.filter(
                response_type__type=self.response_type,
                question__section__marking_session=self.request.current_session,
            )
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

        if response.question.question_type == "negative":
            score = response.points
        elif response.multi_count > 0:
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
            Question.objects.filter(
                section__marking_session=self.request.current_session
            )
            .select_related("section")
            .order_by("section__title", "number", "number_part")
        )

        authorities = PublicAuthority.objects.filter(
            questiongroup__marking_session=self.request.current_session
        )
        authority_map = {}
        for authority in authorities:
            authority_map[authority.name] = {
                "country": authority.country,
                "type": authority.type,
                "political_control": authority.political_control,
                "political_coalition": authority.political_coalition,
            }
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
        context["map"] = authority_map
        context["marks"] = responses

        return context

    def render_to_response(self, context, **response_kwargs):
        response = HttpResponse(
            content_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{self.file_name}"'},
        )
        writer = csv.writer(response)
        authority_map = context["map"]
        headers = [
            "authority",
            "country",
            "type",
            "political_control",
            "coalition",
        ] + context["headers"]
        writer.writerow(headers)
        for authority, mark in context["marks"].items():
            row = [
                authority,
                authority_map[authority]["country"],
                authority_map[authority]["type"],
                authority_map[authority]["political_control"],
                authority_map[authority]["political_coalition"],
            ] + [mark.get(q, "-") for q in context["headers"]]
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


class SelectQuestionView(StatsUserTestMixin, ListView):
    template_name = "crowdsourcer/stats_select_question.html"
    context_object_name = "questions"

    def get_queryset(self):
        return (
            Question.objects.filter(
                section__marking_session=self.request.current_session
            )
            .select_related("section")
            .order_by("section__title", "number", "number_part")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        sections = defaultdict(list)

        for q in context["questions"]:
            sections[q.section.title].append(q)

        # items does not work on defaultdicts in a template :|
        context["sections"] = dict(sections)

        return context


class QuestionDataCSVView(StatsUserTestMixin, ListView):
    context_object_name = "responses"
    response_type = "First Mark"
    headers = [
        "authority",
        "answer",
        "score",
        "public_notes",
        "page_number",
        "evidence",
        "private_notes",
    ]

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
                question__section__marking_session=self.request.current_session,
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
        return get_response_data(
            response, include_private=True, marking_session=self.request.current_session
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        answers = {}

        clear_exception_cache()
        for response in context["responses"]:
            data = self.get_response_data(response)
            answers[response.authority.name] = data

        authorities = []
        for authority in PublicAuthority.objects.filter(
            questiongroup__marking_session=self.request.current_session
        ).order_by("name"):
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


class BaseScoresView(StatsUserTestMixin, TemplateView):
    def get_scores(self):
        clear_exception_cache()
        self.scoring = get_scoring_object(self.request.current_session)

    def render_to_response(self, context, **response_kwargs):
        response = HttpResponse(
            content_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{self.file_name}"'},
        )
        writer = csv.writer(response)
        for row in context["rows"]:
            writer.writerow(row)
        return response


class AllAnswerDataView(BaseScoresView):
    file_name = "all_answer_data.csv"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        args = {}
        if self.request.GET.get("stage"):
            args["response_type"] = self.request.GET["stage"]
            self.file_name = f"all_answer_data_{slugify(args['response_type'])}.csv"

        self.get_scores()
        context["rows"] = get_all_question_data(
            self.scoring, marking_session=self.request.current_session.label, **args
        )

        return context


class WeightedScoresDataCSVView(BaseScoresView):
    file_name = "all_sections_scores.csv"

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
                "country",
                "type",
                "political_control",
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
            country = self.scoring["council_countries"][council]
            council_type = self.scoring["council_type"][council]
            control = self.scoring["council_control"][council]
            for section, scores in council_score.items():
                row = [
                    council,
                    country,
                    council_type,
                    control,
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
            total = self.scoring["council_totals"][council]["weighted_total"]
            rows.append(
                [
                    council,
                    country,
                    council_type,
                    control,
                    "Total",
                    "-",
                    "-",
                    "-",
                    "-",
                    "-",
                    f"{total:.2f}",
                ]
            )

        context["rows"] = rows

        return context


class QuestionScoresCSV(StatsUserTestMixin, ListView):
    context_object_name = "options"

    def get_queryset(self):
        return (
            Option.objects.filter(
                question__section__marking_session=self.request.current_session
            )
            .select_related("question", "question__section")
            .order_by(
                "question__section__title",
                "question__number",
                "question__number_part",
                "score",
            )
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        clear_exception_cache()
        scoring = {}
        get_section_maxes(scoring, self.request.current_session)

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
                    "clarifications": option.question.clarifications,
                    "criteria": option.question.criteria,
                    "how_marked": option.question.how_marked,
                    "type": option.question.question_type,
                    "weighting": option.question.weighting,
                    "raw_max": max_score,
                    "weighted_max": weighting_to_points(
                        option.question.weighting, max_score
                    ),
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
                "weighting",
                "raw max",
                "weighted max",
                "options",
                "clarifications",
                "criteria",
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
                    q["weighting"],
                    q["raw_max"],
                    q["weighted_max"],
                    q["options"],
                    q["clarifications"],
                    q["criteria"],
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


class BadResponsesView(StatsUserTestMixin, ListView):
    context_object_name = "responses"
    template_name = "crowdsourcer/bad_responses.html"

    def get_queryset(self):
        responses = (
            Response.objects.filter(
                response_type__type="Audit",
                option__isnull=True,
                multi_option__isnull=True,
                question__section__marking_session=self.request.current_session,
            )
            .select_related("authority", "question", "question__section")
            .order_by("authority", "question__section")
        )

        return responses


class DuplicateResponsesView(StatsUserTestMixin, ListView):
    context_object_name = "responses"
    template_name = "crowdsourcer/duplicate_responses.html"

    def get_queryset(self):
        response_type = self.request.GET.get("type", "Audit")
        return get_duplicate_responses(
            self.request.current_session, response_type=response_type
        )

    def get_context_data(self, **kwargs):
        ignore_exacts = self.request.GET.get("ignore_exacts", 0)
        response_type = self.request.GET.get("type", "Audit")
        context = super().get_context_data(**kwargs)

        duplicates = context["responses"]

        progress_link = "audit_authority_progress"
        question_link = "authority_audit"

        if response_type == "First Mark":
            progress_link = "authority_progress"
            question_link = "authority_question_edit"
        elif response_type == "Right of Reply":
            progress_link = "authority_ror_progress"
            question_link = "authority_ror"

        exact_duplicates = get_exact_duplicates(
            duplicates, self.request.current_session
        )

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
                response_type__type=response_type,
            ).select_related("authority", "question", "question__section")

            dupe = []
            for r in rs:
                r.dupe_id = f"{r.question_id}:{r.authority_id}"
                dupe.append(r)
            dupes.append(dupe)

        context["progress_link"] = progress_link
        context["question_link"] = question_link
        context["response_type"] = response_type
        context["ignore_exacts"] = ignore_exacts
        context["exact_dupes"] = exact_ids
        context["dupes"] = dupes

        return context


class CouncilHistoryListView(StatsUserTestMixin, ListView):
    context_object_name = "authorities"
    template_name = "crowdsourcer/response_history_authorities.html"

    def get_queryset(self):
        return PublicAuthority.objects.filter(
            marking_session=self.request.current_session
        ).order_by("name")


class CouncilQuestionHistoryListView(SelectQuestionView):
    template_name = "crowdsourcer/response_history_questions.html"

    def get_queryset(self):
        try:
            authority = PublicAuthority.objects.get(name=self.kwargs["authority"])
        except PublicAuthority.DoesNotExist:
            return None

        return (
            Question.objects.filter(
                questiongroup=authority.questiongroup,
                section__marking_session=self.request.current_session,
            )
            .select_related("section")
            .order_by("section__title", "number", "number_part")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        try:
            authority = PublicAuthority.objects.get(name=self.kwargs["authority"])
            context["authority"] = authority
        except PublicAuthority.DoesNotExist:
            context["no_authority"] = True

        return context


class ResponseHistoryView(StatsUserTestMixin, ListView):
    context_object_name = "responses"
    template_name = "crowdsourcer/response_history.html"
    has_duplicates = False

    def get_queryset(self):
        stage = self.kwargs["stage"]
        authority = self.kwargs["authority"]
        question = self.kwargs["question"]

        try:
            response = Response.objects.get(
                question__section__marking_session=self.request.current_session,
                question_id=question,
                authority__name=authority,
                response_type__type=stage,
            )
        except Response.MultipleObjectsReturned:
            self.has_duplicates = True

            responses = Response.objects.filter(
                question__section__marking_session=self.request.current_session,
                question_id=question,
                authority__name=authority,
                response_type__type=stage,
            ).order_by("last_update")
            data = []
            for response in responses:
                data.extend(response.history.all())
            data = sorted(data, key=lambda r: r.last_update)
            return data
        except Response.DoesNotExist:
            return None
        return response.history.all()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        try:
            context["question"] = Question.objects.get(
                section__marking_session=self.request.current_session,
                id=self.kwargs["question"],
            )
        except Question.DoesNotExist:
            context["missing_question"] = True

        context["duplicates"] = self.has_duplicates
        return context


class SessionPropertiesCSVView(StatsUserTestMixin, ListView):
    context_object_name = "properties"

    def get_queryset(self):
        return (
            SessionPropertyValues.objects.filter(
                property__marking_session=self.request.current_session
            )
            .select_related("property", "authority")
            .order_by(
                "authority__name",
                "property__order",
            )
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        rows = []
        rows.append(
            [
                "authority",
                "property",
                "value",
            ]
        )
        for property in context["properties"]:
            rows.append(
                [
                    property.authority.name,
                    property.property.label,
                    property.value,
                ]
            )

        context["rows"] = rows

        return context

    def render_to_response(self, context, **response_kwargs):
        response = HttpResponse(
            content_type="text/csv",
            headers={
                "Content-Disposition": 'attachment; filename="session_properties.csv"'
            },
        )
        writer = csv.writer(response)
        for row in context["rows"]:
            writer.writerow(row)
        return response


class ResponseReportView(StatsUserTestMixin, FilterView):
    template_name = "crowdsourcer/stats/response_report.html"
    context_object_name = "responses"
    filterset_class = ResponseFilter

    def get_filterset(self, filterset_class):
        fs = super().get_filterset(filterset_class)

        fs.filters["question__section"].field.choices = Section.objects.filter(
            marking_session=self.request.current_session
        ).values_list("id", "title")

        questions = Question.objects.filter(
            section__marking_session=self.request.current_session
        ).order_by("section", "number", "number_part")
        if (
            self.request.GET.get("question__section") is not None
            and self.request.GET["question__section"] != ""
        ):
            questions = questions.filter(
                section__id=self.request.GET["question__section"]
            )

        question_choices = [(q.id, q.number_and_part) for q in questions]
        fs.filters["question"].field.choices = question_choices

        options = Option.objects.filter(
            question__section__marking_session=self.request.current_session
        ).order_by("ordering")
        if (
            self.request.GET.get("question") is not None
            and self.request.GET["question"] != ""
        ):
            options = options.filter(question__id=self.request.GET["question"])

        fs.filters["option"].field.choices = options.values_list("id", "description")

        return fs

    def get_queryset(self):
        return Response.objects.filter(
            question__section__marking_session=self.request.current_session
        ).select_related("question", "authority")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        params_required = False
        params = ["question__section", "question", "option", "response_type"]
        for p in params:
            if self.request.GET.get(p) is None or self.request.GET[p] == "":
                params_required = True

        context["params_required"] = params_required

        stage = "First Mark"
        if (
            self.request.GET.get("response_type") is not None
            and self.request.GET["response_type"] != ""
        ):
            stage = ResponseType.objects.get(
                id=self.request.GET.get("response_type")
            ).type
        url_pattern = "authority_question_edit"

        if stage == "Right of Reply":
            url_pattern = "authority_ror"
        elif stage == "Audit":
            url_pattern = "authority_audit"

        context["url_pattern"] = url_pattern
        return context


class AvailableResponseQuestionsView(StatsUserTestMixin, ListView):
    context_object_name = "questions"

    def get_queryset(self):
        if self.request.GET.get("ms") is None or self.request.GET.get("s") is None:
            return []

        marking_session = MarkingSession.objects.get(id=self.request.GET["ms"])
        s = Section.objects.get(
            marking_session=marking_session, id=self.request.GET["s"]
        )
        return Question.objects.filter(section=s).order_by("number", "number_part")

    def render_to_response(self, context, **response_kwargs):
        data = []

        for q in context["questions"]:
            data.append({"number_and_part": q.number_and_part, "id": q.id})

        return JsonResponse({"results": data})


class AvailableResponseOptionsView(StatsUserTestMixin, ListView):
    context_object_name = "options"

    def get_queryset(self):
        if self.request.GET.get("q") is None:
            return []

        q = Question.objects.get(id=self.request.GET["q"])
        return Option.objects.filter(question=q).order_by("ordering")

    def render_to_response(self, context, **response_kwargs):
        data = []

        for o in context["options"]:
            data.append({"description": o.description, "id": o.id})

        return JsonResponse({"results": data})


class CheckAutomaticPointsView(StatsUserTestMixin, TemplateView):
    context_object_name = "responses"
    template_name = "crowdsourcer/changed_automatic_points.html"

    cols = {
        "answer": "answer in GRACE",
        "section": "section",
        "authority_type": "council type",
        "authority_country": "council country",
        "authority_list": "council list",
        "page_number": "page no",
        "public_notes": "evidence link",
        "evidence": "evidence notes",
    }

    def scrub_council_type(self, types):
        type_map = {
            "COMB": "COMB",
            "CTY": "CTY",
            "LGD": "LGD",
            "MD": "MTD",
            "MTD": "MTD",
            "UTA": "UTA",
            "COI": "COI",
            "NMD": "NMD",
            "DIS": "DIS",
            "CC": "LBO",
            "LBO": "LBO",
            "SCO": "UTA",
            "WPA": "UTA",
            "NID": "UTA",
            "UA": "UTA",
            "SRA": "COMB",
        }
        scrubbed = []
        for t in types:
            t = t.strip()
            if type_map.get(t) is not None:
                scrubbed.append(type_map[t])
            else:
                self.print_error(f"bad council type {t}")
        return scrubbed

    def get_config(self):
        try:
            c = SessionConfig.objects.get(
                marking_session=self.request.current_session, name="automatic_points"
            )
            conf = c.value
        except SessionConfig.DoesNotExist:
            conf = {
                "data_subdir": None,
                "points_file": "automatic_points.csv",
                "option_map_file": None,
            }

        return conf

    def get_df(self, file_name, data_subdir=None):
        data_dir = settings.BASE_DIR / "data"
        if data_subdir:
            data_dir = data_dir / data_subdir

        file = data_dir / file_name
        try:
            df = pd.read_csv(file)
        except FileNotFoundError:
            return None

        return df

    def get_points_file(self):
        df = self.get_df(self.conf["points_file"], self.conf.get("data_subdir"))

        if df is not None:
            df[self.cols["answer"]] = df[self.cols["answer"]].astype(str)

        return df

    def get_option_map(self):
        df = self.get_df(self.conf["option_map_file"], self.conf.get("data_subdir"))

        df.question = df.question.astype(str)

        option_map = defaultdict(dict)
        for _, option in df.iterrows():
            if option_map[option["section"]].get(option["question"]) is None:
                option_map[option["section"]][option["question"]] = {}

            option_map[option["section"]][option["question"]][option["prev_option"]] = (
                option["new_option"]
            )

        return option_map

    def get_mapped_answer(self, answer, q, answer_map):
        if (
            answer_map.get(q.section.title) is not None
            and answer_map[q.section.title].get(q.number_and_part) is not None
            and answer_map[q.section.title][q.number_and_part].get(answer) is not None
        ):
            return answer_map[q.section.title][q.number_and_part][answer]

        return answer

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        bad_responses = defaultdict(dict)

        self.conf = self.get_config()

        points = self.get_points_file()
        if points is None:
            context["error"] = "Could not find points file"
            return context

        answer_map = self.get_option_map()

        for _, point in points.iterrows():
            copy_last_year = False
            if point[self.cols["section"]] == "Practice":
                continue

            if pd.isna(point["question number"]):
                continue

            if point[self.cols["section"]] == "":
                continue

            c_args = {}
            if (
                point.get(self.cols["authority_type"]) is not None
                and pd.isna(point[self.cols["authority_type"]]) is False
            ):
                types = point[self.cols["authority_type"]].strip()
                if types != "":
                    types = self.scrub_council_type(types.split(","))
                    c_args["type__in"] = types

            if (
                point.get(self.cols["authority_country"], None) is not None
                and pd.isna(point[self.cols["authority_country"]]) is False
            ):
                countries = point[self.cols["authority_country"]].strip()
                if countries != "":
                    countries = countries.split(",")
                    c_args["country__in"] = [c.lower() for c in countries]

            if (
                point.get(self.cols["authority_list"]) is not None
                and pd.isna(point[self.cols["authority_list"]]) is False
            ):
                councils = point[self.cols["authority_list"]].strip()
                if councils != "" and "Single-Tier" not in councils.split(","):
                    councils = [c.strip() for c in councils.split(",")]
                    c_args = {"name__in": councils}

            councils = PublicAuthority.objects.filter(
                marking_session=self.request.current_session, **c_args
            )
            q_args = {"number": point["question number"]}
            if (
                not pd.isna(point["question part"])
                and point.get("question part", None) is not None
            ):
                q_args["number_part"] = point["question part"].strip()

            try:
                question = Question.objects.get(
                    section__marking_session=self.request.current_session,
                    section__title=point[self.cols["section"]],
                    **q_args,
                )
            except Question.DoesNotExist:
                continue

            if not pd.isna(point["copy last year answer"]):
                if point["copy last year answer"] == "Y":
                    copy_last_year = True

            responses = Response.objects.filter(
                authority__in=councils,
                question=question,
                response_type__type="Audit",
            )
            bad_q_responses = []
            for r in responses.all():
                if copy_last_year:
                    try:
                        prev_response = Response.objects.get(
                            authority=r.authority,
                            question=question.previous_question,
                            response_type__type="Audit",
                        )
                    except Response.DoesNotExist:
                        continue

                    if prev_response.option:
                        past_answer = self.get_mapped_answer(
                            prev_response.option.description, question, answer_map
                        )
                    else:
                        continue
                    page_number = prev_response.page_number
                    if not pd.isna(point[self.cols["page_number"]]):
                        page_number = point[self.cols["page_number"]]

                    public_notes = prev_response.public_notes
                    if not pd.isna(point[self.cols["public_notes"]]):
                        public_notes = point[self.cols["public_notes"]]

                    evidence = prev_response.evidence
                    if not pd.isna(point[self.cols["evidence"]]):
                        evidence = point[self.cols["evidence"]]

                    if (
                        r.option.description != past_answer
                        or r.page_number != page_number
                        or r.public_notes != public_notes
                        or r.evidence != evidence
                    ):
                        bad_response = {
                            "saved": r,
                            "expected": {
                                "option": past_answer,
                                "page_number": page_number,
                                "public_notes": public_notes,
                                "evidence": evidence,
                            },
                        }
                        bad_q_responses.append(bad_response)
                else:
                    answer = self.get_mapped_answer(
                        point[self.cols["answer"]], question, answer_map
                    )

                    if (
                        r.option.description != answer
                        or r.page_number != point["page no"]
                        or r.public_notes != point["evidence link"]
                        or r.evidence != point["evidence notes"]
                    ):
                        bad_response = {
                            "saved": r,
                            "expected": {
                                "option": answer,
                                "page_number": point[self.cols["page_number"]],
                                "public_notes": point[self.cols["public_notes"]],
                                "evidence": point[self.cols["evidence"]],
                            },
                        }
                        bad_q_responses.append(bad_response)

            bad_responses[point[self.cols["section"]]][
                question.number_and_part
            ] = bad_q_responses

        context["bad_responses"] = dict(bad_responses)

        return context
