import re

from django.conf import settings
from django.core.management.base import BaseCommand

import pandas as pd

from crowdsourcer.models import MarkingSession, Option, Question, QuestionGroup, Section


class Command(BaseCommand):
    help = "import CEUK questions"

    question_file = settings.BASE_DIR / "data" / "questions.xlsx"

    column_names = [
        "question_no",
        "topic",
        "question",
        "no_mark_options",
        "criteria",
        "clarifications",
        "how_marked",
        "weighting",
        "climate_justice",
        "district",
        "single_tier",
        "county",
        "northern_ireland",
        "question_type",
        "points",
    ]

    def add_arguments(self, parser):
        parser.add_argument(
            "-q", "--quiet", action="store_true", help="Silence progress bars."
        )

        parser.add_argument(
            "--text_only",
            action="store_true",
            help="Only update question text, criteria and clarifications",
        )

        parser.add_argument(
            "--weighting_only",
            action="store_true",
            help="Only update question weighting",
        )

        parser.add_argument(
            "--session", action="store", help="Marking session to use questions with"
        )

        parser.add_argument(
            "--file", action="store", help="Excel file containing the questions"
        )

        parser.add_argument(
            "--column_list", action="store", help="file with list of column names"
        )

        parser.add_argument(
            "--delete_old_no_mark_options",
            action="store_true",
            help="remove old options with zero marks",
        )

        parser.add_argument(
            "--delete_options",
            action="store_true",
            help="remove all options and recreate",
        )

    def get_column_names(self, **kwargs):
        column_list = kwargs.get("column_list", None)
        column_list = settings.BASE_DIR / "data" / column_list
        if not column_list.exists():
            self.stderr.write(
                f"file does not exist: {column_list}, using standard columns"
            )
            return

        if column_list is not None:
            df = pd.read_csv(settings.BASE_DIR / "data" / column_list)
            columns = []
            for _, row in df.iterrows():
                columns.append(row["Column"])
            self.column_names = columns

    def clean_extra(self, extra):
        if pd.isna(extra) or extra == "" or extra == "nan":
            extra = "n/a"

        return extra

    def handle(self, quiet: bool = False, *args, **kwargs):
        file = kwargs.get("file", None)

        if file is None:
            self.stderr.write("please supply a file name")
            return

        self.question_file = settings.BASE_DIR / "data" / file

        if not self.question_file.exists():
            self.stderr.write(f"file does not exist: {self.question_file}")
            return

        q_groups = {}

        session_label = kwargs.get("session", None)
        try:
            session = MarkingSession.objects.get(label=session_label)
        except MarkingSession.DoesNotExist:
            self.stderr.write(f"No session with that name: {session_label}")
            return

        for q in QuestionGroup.objects.filter(marking_session=session).exclude(
            description="Combined Authority"
        ):
            key = q.description.lower().replace(" ", "_")
            q_groups[key] = q

        self.get_column_names(**kwargs)

        for section in Section.objects.exclude(title__contains="(CA)").filter(
            marking_session=session
        ):
            print(section)
            header = 2
            df = pd.read_excel(
                self.question_file,
                sheet_name=section.title,
            )
            for index, row in df.iterrows():
                q_cell = row.iat[3]
                if type(q_cell) is str and q_cell.strip() == "Question":
                    header = index + 1
                    break

                if index > 5:
                    print(f"Did not find header in {section}")
                    break

            df = pd.read_excel(
                self.question_file,
                sheet_name=section.title,
                header=header,
                usecols=lambda name: "Unnamed" not in name,
            )

            df = df.dropna(axis="index", how="all")
            drop_cols = [
                "Climate Justice/Adaptation Tag",
                "Is this question or criteria changing?",
                "Change proposed",
                "New Criteria",
                "Clarifications",
                "2023 Scorecards Criteria",
                "2023 Scorecards Clarifications",
                "2023 Criteria",
                "2023 Clarifications",
                "Previous Criteria from 2023 Scorecards",
            ]
            for col in drop_cols:
                if col in df.columns:
                    df = df.drop(col, axis=1)
            # df = df.iloc[:, :15]

            columns = list(self.column_names)

            if "Drop down box options for no mark awarded (internal)" not in df.columns:
                columns.remove("no_mark_options")

            options = len(df.columns) - len(columns) + 1
            for i in range(1, options):
                columns.append(f"option_{i}")

            df.columns = columns

            for index, row in df.iterrows():
                q_no = row["question_no"]
                q_part = None
                if pd.isna(q_no):
                    continue

                if pd.isna(row["question"]):
                    continue

                if type(q_no) is not int:
                    q_parts = re.search(r"(\d+)([a-z]?)", q_no).groups()
                    q_no = q_parts[0]
                    if len(q_parts) == 2:
                        q_part = q_parts[1]

                how_marked = "volunteer"
                question_type = "yes_no"
                how_marked_row = str(row["how_marked"]).strip().lower()
                if how_marked_row == "foi":
                    how_marked = "foi"
                    question_type = "foi"
                elif how_marked_row == "national data":
                    how_marked = "national_data"
                    question_type = "national_data"

                if row.get("question_type", None) is not None and not pd.isna(
                    row["question_type"]
                ):
                    q_type = str(row["question_type"]).strip().lower()
                    if q_type == "tiered answer":
                        question_type = "tiered"
                    elif q_type == "tick all that apply":
                        question_type = "multiple_choice"
                    elif q_type == "multiple choice":
                        question_type = "select_one"
                    elif q_type == "negative" or q_type == "negatively marked":
                        question_type = "negative"
                    elif q_type == "y/n":
                        pass
                    else:
                        print(
                            f"missing question type: {section.title}, {row['question_no']} - {row['question_type']}"
                        )
                        continue

                row = row.fillna("")
                weighting = "low"
                if type(row["weighting"]) is str:
                    weighting = str(row["weighting"]).strip().lower()
                else:
                    print(
                        f"bad weighting for {section.title}, {q_no}{q_part}: {row['weighting']}"
                    )
                defaults = {
                    "description": row["question"],
                    "criteria": self.clean_extra(row["criteria"]),
                    "question_type": question_type,
                    "how_marked": how_marked,
                    "clarifications": self.clean_extra(row["clarifications"]),
                    "topic": row["topic"],
                    "weighting": weighting,
                }

                if kwargs["text_only"] or kwargs["weighting_only"]:
                    for default in [
                        "question_type",
                        "how_marked",
                        "topic",
                    ]:
                        del defaults[default]

                if kwargs["text_only"]:
                    del defaults["weighting"]

                if kwargs["weighting_only"]:
                    for default in [
                        "description",
                        "criteria",
                        "clarifications",
                    ]:
                        del defaults[default]

                q, c = Question.objects.update_or_create(
                    number=q_no,
                    number_part=q_part,
                    section=section,
                    defaults=defaults,
                )

                if kwargs["text_only"] or kwargs["weighting_only"]:
                    continue

                if kwargs["delete_old_no_mark_options"]:
                    Option.objects.filter(question=q, score=0).delete()

                if kwargs["delete_options"]:
                    Option.objects.filter(question=q).delete()

                if row.get("no_mark_options") is not None:
                    no_mark_options = row["no_mark_options"].splitlines()
                else:
                    no_mark_options = []

                if q.question_type != "yes_no":
                    no_mark_options.extend(
                        [
                            "No Penalty Mark",
                            "No evidence found",
                            "Evidence does not meet criteria",
                            "No response from FOI",
                        ]
                    )

                if q.question_type in ["select_one", "tiered", "multiple_choice"]:
                    if not no_mark_options:
                        o, c = Option.objects.update_or_create(
                            question=q,
                            description="None",
                            defaults={"score": 0, "ordering": 100},
                        )
                    no_mark_seen = 0
                    for i in range(1, options):
                        option_col = f"option_{i}"
                        desc = str(row[option_col]).strip()
                        # do this slightly odd thing because the str conversion on a na will get
                        # you nan but need to do str etc to check for blank. Can't do this as
                        # a bulk operation on the df as we don't know how many option cols there are
                        if pd.isna(row[option_col]) or desc == "":
                            continue
                        score = 1
                        ordering = i
                        if q.question_type == "tiered":
                            score = i - no_mark_seen
                        if desc in no_mark_options:
                            no_mark_seen = no_mark_seen + 1
                            score = 0
                            ordering = 100 + ordering
                        o, c = Option.objects.update_or_create(
                            question=q,
                            description=desc,
                            defaults={"score": score, "ordering": ordering},
                        )
                elif q.question_type == "yes_no":
                    o, c = Option.objects.update_or_create(
                        question=q,
                        description="Yes",
                        defaults={"score": 1, "ordering": 1},
                    )
                    if no_mark_options:
                        for option in no_mark_options:
                            o, c = Option.objects.update_or_create(
                                question=q,
                                description=option,
                                defaults={"score": 0, "ordering": 100},
                            )
                    else:
                        o, c = Option.objects.update_or_create(
                            question=q,
                            description="No",
                            defaults={"score": 0, "ordering": 2},
                        )

                q.questiongroup.clear()
                for col, group in q_groups.items():
                    if row[col] in ["Yes", "Y", "All"]:
                        q.questiongroup.add(group)
