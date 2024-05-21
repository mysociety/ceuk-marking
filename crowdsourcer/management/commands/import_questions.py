import re

from django.conf import settings
from django.core.management.base import BaseCommand

import pandas as pd

from crowdsourcer.models import MarkingSession, Option, Question, QuestionGroup, Section


class Command(BaseCommand):
    help = "import questions"

    column_names = [
        "question_no",
        "question",
        "criteria",
        "clarifications",
        "weighting",
        "question_groups",
        "question_type",
        "points",
    ]

    def add_arguments(self, parser):
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

    def handle(self, *args, **kwargs):
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

        for q in QuestionGroup.objects.filter(marking_session=session):
            q_groups[q.description] = q

        for section in Section.objects.filter(marking_session=session):
            print(f"importing questions for {section}")
            df = pd.read_excel(
                self.question_file,
                sheet_name=section.title,
                header=1,
            )

            df = df.dropna(axis="index", how="all")
            df = df.iloc[:, :14]

            columns = list(self.column_names)
            options = len(df.columns) - len(self.column_names) + 1
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

                question_type = "yes_no"

                if row.get("question_type", None) is not None and not pd.isna(
                    row["question_type"]
                ):
                    if row["question_type"].lower() == "tiered answer":
                        question_type = "tiered"
                    elif row["question_type"].lower() == "tick all that apply":
                        question_type = "multiple_choice"
                    elif row["question_type"].lower() == "multiple choice":
                        question_type = "select_one"

                row = row.fillna("")
                defaults = {
                    "description": row["question"],
                    "criteria": row["criteria"],
                    "question_type": question_type,
                    "how_marked": "volunteer",
                    "clarifications": row["clarifications"],
                    "topic": "",
                    "weighting": row["weighting"],
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

                if q.question_type in ["select_one", "tiered", "multiple_choice"]:
                    o, c = Option.objects.update_or_create(
                        question=q,
                        description="None",
                        defaults={"score": 0, "ordering": 100},
                    )
                    for i in range(1, options):
                        desc = row[f"option_{i}"]
                        if pd.isna(desc) or desc.strip() == "":
                            continue

                        score = 1
                        ordering = i
                        if q.question_type == "tiered":
                            score = i

                        o, c = Option.objects.update_or_create(
                            question=q,
                            description=desc,
                            defaults={"score": score, "ordering": ordering},
                        )
                elif q.question_type == "yes_no":
                    for desc in ["Yes", "No"]:
                        ordering = 1
                        score = 1
                        if desc == "No":
                            score = 0
                            ordering = 2
                        o, c = Option.objects.update_or_create(
                            question=q,
                            description=desc,
                            defaults={"score": score, "ordering": ordering},
                        )

                for group in row["question_groups"].split("|"):
                    q.questiongroup.add(q_groups[group])
