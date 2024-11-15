from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils.text import slugify

import pandas as pd

from crowdsourcer.models import MarkingSession, Question
from crowdsourcer.scoring import (
    clear_exception_cache,
    get_all_question_data,
    get_scoring_object,
)


class Command(BaseCommand):
    help = "export processed mark data"

    def make_file_names(self, session):
        session_slug = slugify(session)
        base_dir = settings.BASE_DIR / "data" / session_slug
        base_dir.mkdir(mode=0o755, exist_ok=True)

        self.section_scores_file = base_dir / "raw_sections_marks.csv"
        self.council_section_scores_file = base_dir / "raw_council_section_marks.csv"
        self.total_scores_file = base_dir / "all_section_scores.csv"
        self.question_scores_file = base_dir / "individual_answers.csv"
        self.questions_file = base_dir / "questions.csv"

    def add_arguments(self, parser):
        parser.add_argument(
            "-q", "--quiet", action="store_true", help="Silence progress bars."
        )

        parser.add_argument(
            "--output_answers", action="store_true", help="Output the all answers file"
        )

        parser.add_argument(
            "--session", action="store", help="Name of the marking session to use"
        )

        parser.add_argument(
            "--questions_only",
            action="store_true",
            help="Only output questions. not marks",
        )

    def write_files(
        self, percent_marks, raw_marks, linear, answers=None, questions=None
    ):
        if not self.questions_only:
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
        self,
        quiet: bool = False,
        output_answers: bool = False,
        questions_only: bool = False,
        *args,
        **options,
    ):
        self.questions_only = questions_only

        # make sure we're not using old cached exceptions
        clear_exception_cache()
        session_label = options["session"]
        try:
            session = MarkingSession.objects.get(label=session_label)
        except MarkingSession.DoesNotExist:
            self.stderr.write(f"No such session: {session_label}")
            sessions = [s.label for s in MarkingSession.objects.all()]
            self.stderr.write(f"Available sessions are {sessions}")
            return

        self.session = session
        self.make_file_names(session_label)

        raw = []
        percent = []
        linear = []
        scoring = {}

        if not questions_only:
            scoring = get_scoring_object(session)

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
                p["weighted_total"] = scoring["council_totals"][council][
                    "weighted_total"
                ]
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
        if output_answers or questions_only:
            if not questions_only:
                answer_data = get_all_question_data(
                    scoring, marking_session=session.label
                )

            questions = (
                Question.objects.filter(section__marking_session=session)
                .order_by("section__title", "number", "number_part")
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
                if (
                    not questions_only
                    and scoring["q_maxes"][section].get(q_no, None) is not None
                ):
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
        elif questions_only:
            self.write_files(percent, raw, linear, questions=question_data)
        else:
            self.write_files(percent, raw, linear)
