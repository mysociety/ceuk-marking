import re

from django.conf import settings
from django.core.management.base import BaseCommand

import pandas as pd

from crowdsourcer.models import Option, Question, QuestionGroup, Section


class Command(BaseCommand):
    help = "import questions"

    question_file = settings.BASE_DIR / "data" / "combined_authority_questions.xlsx"

    column_names = [
        "question_no",
        "topic",
        "question",
        "criteria",
        "clarifications",
        "how_marked",
        "total_points",
        "weighting",
        "new_amend",
        "question_type",
        "points",
    ]

    # get round limits on length of sheet names
    sheet_map = {
        "Buildings & Heating & Green Skills": "Buildings & Heating & Green Ski",
    }

    def add_arguments(self, parser):
        parser.add_argument(
            "-q", "--quiet", action="store_true", help="Silence progress bars."
        )

        parser.add_argument(
            "--text_only",
            action="store_true",
            help="Only update question text, criteria and clarifications",
        )

    def handle(self, quiet: bool = False, *args, **kwargs):
        group = QuestionGroup.objects.get(description="Combined Authority")

        for section in Section.objects.filter(title__contains="(CA)"):
            title = section.title.replace(" (CA)", "")
            df = pd.read_excel(
                self.question_file,
                sheet_name=self.sheet_map.get(title, title),
                header=2,
                # remove blank and hidden notes columns
                usecols=lambda name: name != "Notes" and "Unnamed" not in name,
            )

            df = df.dropna(axis="index", how="all")

            columns = list(self.column_names)
            options = len(df.columns) - len(self.column_names) + 1
            for i in range(1, options):
                columns.append(f"option_{i}")

            df.columns = columns

            for index, row in df.iterrows():
                if pd.isna(row["question_no"]):
                    continue

                q_no = str(row["question_no"])
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
                if not kwargs["text_only"]:
                    if row["how_marked"] == "FOI":
                        how_marked = "foi"
                        question_type = "foi"
                    elif "National Data" in row["how_marked"]:
                        how_marked = "national_data"
                        question_type = "national_data"

                    if not pd.isna(row["question_type"]):
                        if row["question_type"] == "Tiered answer":
                            question_type = "tiered"
                        elif row["question_type"] == "Tick all that apply":
                            question_type = "multiple_choice"
                        elif row["question_type"] in [
                            "Multiple choice",
                            "Multiple",
                            "multiple",
                        ]:
                            question_type = "select_one"
                        elif row["question_type"] == "Y/N":
                            pass
                        else:
                            print(
                                f"missing question type: {title}, {row['question_no']} - {row['question_type']}"
                            )
                            continue

                defaults = {
                    "description": row["question"],
                    "criteria": row["criteria"],
                    "question_type": question_type,
                    "how_marked": how_marked,
                    "clarifications": row["clarifications"],
                    "topic": row["topic"],
                }

                if kwargs["text_only"]:
                    for default in [
                        "question_type",
                        "how_marked",
                        "topic",
                    ]:
                        del defaults[default]

                q, c = Question.objects.update_or_create(
                    number=q_no,
                    number_part=q_part,
                    section=section,
                    defaults=defaults,
                )

                if kwargs["text_only"]:
                    continue

                if q.question_type in ["select_one", "tiered", "multiple_choice"]:
                    is_no = False
                    for i in range(1, options):
                        desc = row[f"option_{i}"]
                        score = 1
                        ordering = i
                        if q.question_type == "tiered":
                            score = i
                        if not pd.isna(desc):
                            if desc == "No":
                                is_no = True
                            o, c = Option.objects.update_or_create(
                                question=q,
                                description=desc,
                                defaults={"score": score, "ordering": ordering},
                            )

                    if not is_no and q.question_type == "tiered":
                        o, c = Option.objects.update_or_create(
                            question=q,
                            description="None",
                            defaults={"score": 0, "ordering": 100},
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

                q.questiongroup.add(group)
