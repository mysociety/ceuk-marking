from django.conf import settings
from django.core.management.base import BaseCommand

import pandas as pd

from crowdsourcer.models import PublicAuthority
from crowdsourcer.scoring import (
    calculate_council_totals,
    get_section_maxes,
    get_section_scores,
)


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
        raw = []
        percent = []
        linear = []

        council_gss_map, groups = PublicAuthority.maps()
        maxes, group_maxes, q_maxes, weighted_maxes = get_section_maxes()
        raw_scores, weighted = get_section_scores(q_maxes)

        council_totals, section_totals = calculate_council_totals(
            raw_scores, weighted, weighted_maxes, maxes, group_maxes, groups
        )

        for council, council_score in section_totals.items():
            p = {"council": council, "gss": council_gss_map[council]}
            raw_sections = {}
            for section, scores in council_score.items():
                raw_sections[section] = scores["raw"]
                linear.append(
                    (
                        council,
                        council_gss_map[council],
                        section,
                        scores["raw"],
                        maxes[section][groups[council]],
                    )
                )
                p[section] = scores["raw_percent"]

            p["raw_total"] = council_totals[council]["percent_total"]
            p["weighted_total"] = council_totals[council]["weighted_total"]
            row = {
                **raw_sections,
                **{
                    "council": council,
                    "gss": council_gss_map[council],
                    "total": council_totals[council]["raw_total"],
                },
            }
            raw.append(row)
            percent.append(p)

        self.write_files(percent, raw, linear)
