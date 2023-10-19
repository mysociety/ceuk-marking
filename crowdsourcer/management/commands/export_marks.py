from django.conf import settings
from django.core.management.base import BaseCommand

import pandas as pd

from crowdsourcer.models import Question
from crowdsourcer.scoring import get_all_question_data, get_scoring_object


class Command(BaseCommand):
    help = "export processed mark data"

    section_scores_file = settings.BASE_DIR / "data" / "raw_sections_marks.csv"
    council_section_scores_file = (
        settings.BASE_DIR / "data" / "raw_council_section_marks.csv"
    )
    total_scores_file = settings.BASE_DIR / "data" / "all_section_scores.csv"
    question_scores_file = settings.BASE_DIR / "data" / "individual_answers.csv"
    questions_file = settings.BASE_DIR / "data" / "questions.csv"

    def add_arguments(self, parser):
        parser.add_argument(
            "-q", "--quiet", action="store_true", help="Silence progress bars."
        )

        parser.add_argument(
            "--output_answers", action="store_true", help="Output the all answers file"
        )

    def write_files(
        self, percent_marks, raw_marks, linear, answers=None, questions=None
    ):
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
            df = pd.DataFrame(answers)
            df = df.rename(columns=df.iloc[0]).drop(df.index[0])
            df = df.set_index("council name")
            df.to_csv(self.question_scores_file)

        if questions is not None:
            df = pd.DataFrame(questions, index=None)
            df = df.rename(columns=df.iloc[0]).drop(df.index[0])
            df = df.set_index("question_number")
            df.to_csv(self.questions_file)

    def handle(
        self, quiet: bool = False, output_answers: bool = False, *args, **options
    ):
        raw = []
        percent = []
        linear = []

        scoring = get_scoring_object()

        for council, council_score in scoring["section_totals"].items():

            p = {
                "council": council,
                "gss": scoring["council_gss_map"][council],
                "political_control": scoring["council_control"][council],
            }
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
                p[section] = scores["unweighted_percentage"]

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

            questions = (
                Question.objects.order_by("section__title", "number", "number_part")
                .select_related("section")
                .all()
            )

            question_data = [
                [
                    "question_number",
                    "section",
                    "description",
                    "type",
                    "max_score",
                    "weighting",
                    "how_marked",
                    "criteria",
                    "topic",
                    "clarifications",
                    "groups",
                ]
            ]

            for question in questions:
                section = question.section.title
                q_no = question.number_and_part

                max_score = 0
                if scoring["q_maxes"][section].get(q_no, None) is not None:
                    max_score = scoring["q_maxes"][section][q_no]

                groups = [g.description for g in question.questiongroup.all()]

                question_data.append(
                    [
                        question.number_and_part,
                        question.section.title,
                        question.description,
                        question.question_type,
                        max_score,
                        question.weighting,
                        question.how_marked,
                        question.criteria,
                        question.topic,
                        question.clarifications,
                        ",".join(groups),
                    ]
                )

        if output_answers:
            self.write_files(percent, raw, linear, answer_data, question_data)
        else:
            self.write_files(percent, raw, linear)
