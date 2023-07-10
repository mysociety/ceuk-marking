from collections import defaultdict

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.models import Max, OuterRef, Q, Subquery, Sum

import pandas as pd

from crowdsourcer.models import (
    Option,
    PublicAuthority,
    Question,
    QuestionGroup,
    Response,
    Section,
)

section_weightings = {
    "Buildings & Heating": {
        "Single Tier": 0.20,
        "District": 0.25,
        "County": 0.20,
        "Northern Ireland": 0.20,
    },
    "Transport": {
        "Single Tier": 0.20,
        "District": 0.05,
        "County": 0.30,
        "Northern Ireland": 0.15,
    },
    "Planning & Land Use": {
        "Single Tier": 0.15,
        "District": 0.25,
        "County": 0.05,
        "Northern Ireland": 0.15,
    },
    "Governance & Finance": {
        "Single Tier": 0.15,
        "District": 0.15,
        "County": 0.15,
        "Northern Ireland": 0.20,
    },
    "Biodiversity": {
        "Single Tier": 0.10,
        "District": 0.10,
        "County": 0.10,
        "Northern Ireland": 0.10,
    },
    "Collaboration & Engagement": {
        "Single Tier": 0.10,
        "District": 0.10,
        "County": 0.10,
        "Northern Ireland": 0.10,
    },
    "Waste Reduction & Food": {
        "Single Tier": 0.10,
        "District": 0.10,
        "County": 0.10,
        "Northern Ireland": 0.10,
    },
    "Transport (CA)": {
        "Combined Authority": 0.25,
    },
    "Buildings, Heating & Green Skills (CA)": {
        "Combined Authority": 0.25,
    },
    "Governance & Finance (CA)": {
        "Combined Authority": 0.20,
    },
    "Planning, Biodiversity & Land Use (CA)": {
        "Combined Authority": 0.10,
    },
    "Collaboration & Engagement (CA)": {
        "Combined Authority": 0.20,
    },
}


class Command(BaseCommand):
    help = "export processed mark data"

    section_scores_file = settings.BASE_DIR / "data" / "raw_sections_marks.csv"
    council_section_scores_file = (
        settings.BASE_DIR / "data" / "raw_council_section_marks.csv"
    )
    total_scores_file = settings.BASE_DIR / "data" / "all_section_scores.csv"

    def add_arguments(self, parser):
        parser.add_argument(
            "-q", "--quiet", action="store_true", help="Silence progress bars."
        )

    def number_and_part(self, number=None, number_part=None):
        if number_part is not None:
            return f"{number}{number_part}"
        return f"{number}"

    def weighting_to_points(self, weighting="low"):
        weighting = weighting.lower()
        points = 1
        if weighting == "medium":
            points = 2
        elif weighting == "high":
            points = 3

        return points

    def get_section_max(self):
        section_maxes = defaultdict(dict)
        section_weighted_maxes = defaultdict(dict)
        group_totals = defaultdict(int)
        q_maxes = defaultdict(int)

        for section in Section.objects.all():
            q_section_maxes = {}
            for group in QuestionGroup.objects.all():
                questions = Question.objects.filter(
                    section=section, questiongroup=group
                )

                maxes = (
                    Option.objects.filter(
                        question__in=questions,
                        question__question_type__in=["yes_no", "select_one"],
                    )
                    .select_related("question")
                    .values("question__pk", "question__number", "question__number_part")
                    .annotate(highest=Max("score"))
                )
                totals = (
                    Option.objects.filter(question__in=questions)
                    .exclude(question__question_type__in=["yes_no", "select_one"])
                    .select_related("question")
                    .values("question__pk", "question__number", "question__number_part")
                    .annotate(highest=Sum("score"))
                )

                max_score = 0
                for m in maxes:
                    q_section_maxes[
                        self.number_and_part(
                            m["question__number"], m["question__number_part"]
                        )
                    ] = m["highest"]
                    max_score += m["highest"]

                for m in totals:
                    q_section_maxes[
                        self.number_and_part(
                            m["question__number"], m["question__number_part"]
                        )
                    ] = m["highest"]
                    max_score += m["highest"]

                weighted_max = 0
                for q in questions:
                    weighted_max += self.weighting_to_points(q.weighting)

                section_maxes[section.title][group.description] = max_score
                section_weighted_maxes[section.title][group.description] = weighted_max
                group_totals[group.description] += max_score
                q_maxes[section.title] = q_section_maxes.copy()

        return section_maxes, group_totals, q_maxes, section_weighted_maxes

    def write_files(self, percent_marks, raw_marks, linear):
        df = pd.DataFrame.from_records(percent_marks, index="council")
        df.to_csv(self.total_scores_file)

        df = pd.DataFrame.from_records(raw_marks, index="council")
        df.to_csv(self.council_section_scores_file)

        df = pd.DataFrame.from_records(
            linear,
            columns=["council", "gss", "section", "score", "max_score"],
            index="council",
        )
        df.to_csv(self.section_scores_file)

    def handle(self, quiet: bool = False, *args, **options):
        council_gss_map = {}
        raw = []
        percent = []
        linear = []
        groups = {}
        raw_scores = defaultdict(dict)
        weighted = defaultdict(dict)

        maxes, group_maxes, q_maxes, weighted_maxes = self.get_section_max()

        non_ca_sections = {
            x: 0
            for x in Section.objects.exclude(title__contains="(CA)").values_list(
                "title", flat=True
            )
        }
        ca_sections = {
            x: 0
            for x in Section.objects.filter(title__contains="(CA)").values_list(
                "title", flat=True
            )
        }

        for council in PublicAuthority.objects.filter(do_not_mark=False).all():
            council_gss_map[council.name] = council.unique_id
            groups[council.name] = council.questiongroup.description
            if council.type == "COMB":
                weighted[council.name] = ca_sections.copy()
                raw_scores[council.name] = ca_sections.copy()
            else:
                weighted[council.name] = non_ca_sections.copy()
                raw_scores[council.name] = non_ca_sections.copy()

        for section in Section.objects.all():
            scores = (
                Response.objects.filter(
                    response_type__type="Audit", question__section=section
                )
                .annotate(
                    score=Subquery(
                        Option.objects.filter(
                            Q(pk=OuterRef("option"))
                            | Q(pk__in=OuterRef("multi_option"))
                        )
                        .values("question")
                        .annotate(total=Sum("score"))
                        .values("total")
                    )
                )
                .select_related("authority")
            )

            raw_scores_qs = scores.values("authority__name").annotate(
                total=Sum("score")
            )

            for score in raw_scores_qs:
                raw_scores[score["authority__name"]][section.title] = score["total"]

            scores = scores.select_related("questions").values(
                "score",
                "authority__name",
                "question__number",
                "question__number_part",
                "question__weighting",
            )

            for score in scores:
                q = self.number_and_part(
                    score["question__number"], score["question__number_part"]
                )
                q_max = q_maxes[section.title][q]
                weighted_score = (score["score"] / q_max) * self.weighting_to_points(
                    score["question__weighting"]
                )
                weighted[score["authority__name"]][section.title] += weighted_score

        for council, council_score in raw_scores.items():
            total = 0
            weighted_total = 0
            p = {"council": council, "gss": council_gss_map[council]}
            for section, score in council_score.items():
                linear.append(
                    (
                        council,
                        council_gss_map[council],
                        section,
                        score,
                        maxes[section][groups[council]],
                    )
                )
                p[section] = score / maxes[section][groups[council]]
                weighted_total += (
                    weighted[council][section]
                    / weighted_maxes[section][groups[council]]
                ) * section_weightings[section][groups[council]]
                total += score

            p["raw_total"] = total / group_maxes[groups[council]]
            p["weighted_total"] = weighted_total
            row = {
                **council_score,
                **{"council": council, "gss": council_gss_map[council], "total": total},
            }
            raw.append(row)
            percent.append(p)

        self.write_files(percent, raw, linear)
