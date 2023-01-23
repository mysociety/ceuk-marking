import re

from django.conf import settings
from django.core.management.base import BaseCommand

import pandas as pd

from crowdsourcer.models import Option, Question, QuestionGroup, Section


class Command(BaseCommand):
    help = "import questions"

    question_file = settings.BASE_DIR / "data" / "questions.xlsx"

    column_names = [
        "question_no",
        "topic",
        "question",
        "criteria",
        "clarifications",
        "how_marked",
        "climate_justice",
        "weighting",
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

    def handle(self, quiet: bool = False, *args, **options):
        q_groups = {}
        for q in QuestionGroup.objects.all():
            key = q.description.lower().replace(" ", "_")
            q_groups[key] = q

        for section in Section.objects.all():
            df = pd.read_excel(
                self.question_file,
                sheet_name=section.title,
                header=2,
                usecols=lambda name: "Unnamed" not in name,
            )

            df = df.dropna(axis="index", how="all")

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

                if type(q_no) is not int:
                    q_parts = re.search(r"(\d+)([a-z]?)", q_no).groups()
                    q_no = q_parts[0]
                    if len(q_parts) == 2:
                        q_part = q_parts[1]

                how_marked = "volunteer"
                question_type = "yes_no"
                if row["how_marked"] == "FOI":
                    how_marked = "foi"
                    question_type = "foi"
                elif row["how_marked"] == "National Data":
                    how_marked = "national_data"
                    question_type = "national_data"

                if not pd.isna(row["question_type"]):
                    if row["question_type"] == "Tiered answer":
                        question_type = "tiered"
                    elif row["question_type"] == "Tick all that apply":
                        question_type = "multiple_choice"
                    elif row["question_type"] == "Multiple choice":
                        question_type = "select_one"

                q, c = Question.objects.update_or_create(
                    number=q_no,
                    number_part=q_part,
                    section=section,
                    defaults={
                        "description": row["question"],
                        "criteria": row["criteria"],
                        "question_type": question_type,
                        "how_marked": how_marked,
                        "clarifications": row["clarifications"],
                        "topic": row["topic"],
                    },
                )

                if q.question_type in ["select_one", "tiered", "multiple_choice"]:
                    o, c = Option.objects.update_or_create(
                        question=q,
                        description="None",
                        defaults={"score": 0, "ordering": 100},
                    )
                    for i in range(1, options):
                        desc = row[f"option_{i}"]
                        score = 1
                        ordering = i
                        if q.question_type == "tiered":
                            score = i
                        if not pd.isna(desc):
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

                for col, group in q_groups.items():
                    if row[col] == "Yes":
                        q.questiongroup.add(group)
