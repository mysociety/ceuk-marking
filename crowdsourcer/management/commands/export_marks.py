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


class Command(BaseCommand):
    help = "export processed mark data"

    section_scores_file = settings.BASE_DIR / "data" / "raw_sections_marks.csv"
    total_scores_file = settings.BASE_DIR / "data" / "all_section_scores.csv"

    def add_arguments(self, parser):
        parser.add_argument(
            "-q", "--quiet", action="store_true", help="Silence progress bars."
        )

    def get_group(self, props):
        group = "District"

        print(props["name"], props["type"])
        if props["type"] == "LGD":
            group = "Northern Ireland"
        elif props["country"] == "W":
            group = "Single Tier"
        elif props["country"] == "S":
            group = "Single Tier"
        elif props["type"] in ["CC", "MTD", "LBO", "UTA"]:
            group = "Single Tier"
        elif props["type"] in ["CTY"]:
            group = "County"

        g = QuestionGroup.objects.get(description=group)
        return g

    def get_section_max(self):
        section_maxes = defaultdict(dict)
        group_totals = defaultdict(int)

        for section in Section.objects.all():
            for group in QuestionGroup.objects.all():
                questions = Question.objects.filter(
                    section=section, questiongroup=group
                )

                maxes = (
                    Option.objects.filter(
                        question__in=questions,
                        question__question_type__in=["yes_no", "select_one"],
                    )
                    .values("question__pk")
                    .annotate(highest=Max("score"))
                )
                totals = (
                    Option.objects.filter(question__in=questions)
                    .exclude(question__question_type__in=["yes_no", "select_one"])
                    .values("question__pk")
                    .annotate(highest=Sum("score"))
                )

                max_score = 0
                for m in maxes:
                    max_score += m["highest"]

                for m in totals:
                    max_score += m["highest"]

                section_maxes[section.title][group.description] = max_score
                group_totals[group.description] += max_score

        return section_maxes, group_totals

    def write_files(self, percent_marks, raw_marks):
        df = pd.DataFrame.from_records(percent_marks, index="council")
        df.to_csv(self.total_scores_file)

        df = pd.DataFrame.from_records(raw_marks, index="council")
        df.to_csv(self.section_scores_file)

    def handle(self, quiet: bool = False, *args, **options):
        raw = []
        percent = []
        groups = {}
        raw_scores = defaultdict(dict)

        maxes, group_maxes = self.get_section_max()

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
            groups[council.name] = council.questiongroup.description
            if council.type == "COMB":
                raw_scores[council.name] = ca_sections.copy()
            else:
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
                .values("authority__name")
                .annotate(total=Sum("score"))
            )

            for score in scores:
                raw_scores[score["authority__name"]][section.title] = score["total"]

        for council, council_score in raw_scores.items():
            total = 0
            p = {"council": council}
            for section, score in council_score.items():
                p[section] = score / maxes[section][groups[council]]
                total += score

            p["total"] = total / group_maxes[groups[council]]
            row = {**council_score, **{"council": council, "total": total}}
            raw.append(row)
            percent.append(p)

        self.write_files(percent, raw)
