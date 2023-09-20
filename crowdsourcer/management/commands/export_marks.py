from django.conf import settings
from django.core.management.base import BaseCommand

import pandas as pd

from crowdsourcer.scoring import get_all_question_data, get_scoring_object


class Command(BaseCommand):
    help = "export processed mark data"

    section_scores_file = settings.BASE_DIR / "data" / "raw_sections_marks.csv"
    council_section_scores_file = (
        settings.BASE_DIR / "data" / "raw_council_section_marks.csv"
    )
    total_scores_file = settings.BASE_DIR / "data" / "all_section_scores.csv"
    question_scores_file = settings.BASE_DIR / "data" / "individual_answers.csv"

    def add_arguments(self, parser):
        parser.add_argument(
            "-q", "--quiet", action="store_true", help="Silence progress bars."
        )

        parser.add_argument(
            "--output_answers", action="store_true", help="Output the all answers file"
        )

    def write_files(self, percent_marks, raw_marks, linear, answers=None):
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

        if answers is not None:
            df = pd.DataFrame.from_records(answers)
            df.to_csv(self.question_scores_file)

    def handle(
        self, quiet: bool = False, output_answers: bool = False, *args, **options
    ):
        raw = []
        percent = []
        linear = []

        scoring = get_scoring_object()

        for council, council_score in scoring["section_totals"].items():

            p = {"council": council, "gss": scoring["council_gss_map"][council]}
            raw_sections = {}
            for section, scores in council_score.items():
                raw_sections[section] = scores["raw"]
                linear.append(
                    (
                        council,
                        scoring["council_gss_map"][council],
                        section,
                        scores["raw"],
                        scoring["council_maxes"][council]["raw"][section][
                            scoring["council_groups"][council]
                        ],
                    )
                )
                p[section] = scores["raw_percent"]

            p["raw_total"] = scoring["council_totals"][council]["percent_total"]
            p["weighted_total"] = scoring["council_totals"][council]["weighted_total"]
            row = {
                **raw_sections,
                **{
                    "council": council,
                    "gss": scoring["council_gss_map"][council],
                    "total": scoring["council_totals"][council]["raw_total"],
                },
            }
            raw.append(row)
            percent.append(p)

        answer_data = None
        if output_answers:
            answer_data = get_all_question_data(scoring)

        if output_answers:
            self.write_files(percent, raw, linear, answer_data)
        else:
            self.write_files(percent, raw, linear)
