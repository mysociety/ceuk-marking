import math
import numbers
import re

from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

import pandas as pd

from crowdsourcer.models import (
    Option,
    PublicAuthority,
    Question,
    Response,
    ResponseType,
)


class Command(BaseCommand):
    help = "import questions"

    question_file = settings.BASE_DIR / "data" / "national_data.xlsx"

    sheets = {
        "Planning Q10B (pivot table) - Renewable Energy": {
            "section": "Planning & Land Use",
            "number": 10,
            "number_part": "b",
            # "council_col": "Planning Authority",
            # "score_col": "COUNTA of Ref ID for Planning Applications",
        },
        # XXX - what?
        # "Planning Q10B (pivot table) - Renewable Energy": {
        # "section": "Planning & Land Use",
        # "number": 11,
        # },
        "Recycling": {
            "section": "Waste Reduction & Food",
            "number": 8,
            "header_row": 2,
            "council_col": "Local Authority 2020/21",
            "score_col": "Mark",
            # XXX - tiered
            "type": "select_one",
            "options": [
                {"desc": "Criteria not met", "score": 0},
                {"desc": "50% recycling rate", "score": 1},
                {"desc": "60% recycling rate", "score": 2},
                {"desc": "70% recycling rate", "score": 3},
            ]
            # "options": [{"desc": "Criteria not met", "score": 0},]
        },
        "Residual Waste": {
            "section": "Waste Reduction & Food",
            "number": 9,
            "header_row": 1,
            "council_col": "Local Authority 2020/21",
            "score_col": "Mark",
            # XXX - tiered
            "type": "select_one",
            "options": [
                {"desc": "Criteria not met", "score": 0},
                {"desc": "300-400kg residual waste per household", "score": 1},
                {"desc": "Less than 300kg residual waste per household", "score": 2},
            ],
        },
        "Transport Q4 - 20mph": {
            "section": "Transport",
            "number": 4,
            "council_col": "Council name",
            "score_col": "Award point - only 1 tier",
            "type": "yes_no",
        },
        # XXX - no criteria yet
        "Transport Q6 - Active Travel England scores": {
            "section": "Transport",
            "number": 6,
            "header_row": 1,
            "council_col": "Local Authority",
            "score_col": "Front end to show",
        },
        "Transport 8B - Bus Ridership": {
            "section": "Transport",
            "number": 8,
            "number_part": "b",
            "header_row": 2,
            "council_col": "Local Authority",
            "score_col": "Front end to show",
            # XXX - may be tiered
            "type": "select_one",
            "options": [
                {"desc": "Criteria not met", "score": 0},
                {"desc": "75 journeys per head of population", "score": 1},
                {"desc": "150 journeys per head of population", "score": 2},
            ],
        },
        # "still to add": {"section": "Transport", "number": 10},
        # XXX - no data in sheet
        "Transport 12a - Air Quality NO2": {
            "section": "Transport",
            "number": 12,
            "number_part": "a",
        },
        # XXX - no data in sheet
        "Transport 12b - Air Quality PM2.5": {
            "section": "Transport",
            "number": 12,
            "number_part": "b",
        },
        "Biodiversity Q4 - Wildlife Sites ": {
            "section": "Biodiversity",
            "number": 4,
            "header_row": 2,
            "council_col": "Council",
            "score_col": "Point awarded",
            "type": "yes_no",
        },
        "Biodiversity Q7 - Green Flag Awards (pivot table)": {
            "section": "Biodiversity",
            "number": 7,
            # XXX - pivot table confuses pandas :|
            # "council_col": "Managing Organisations",
            # "score_col": "Weighted Question Score to be applied",
            # "weighted": True,
            # XXX - may be tiered
            "type": "select_one",
            "options": [
                {"desc": "Criteria not met", "score": 0},
                {"desc": "At least one Green Flag Park", "score": 1},
                {"desc": "4 or more Green Flag parks", "score": 2},
            ],
        },
        "Gov&Fin Q11a": {
            "section": "Governance & Finance",
            "number": 11,
            "number_part": "a",
            "council_col": "Council",
            "weighted": 2,
            "score_col": "Score",
            "type": "select_one",
            "options": [
                {"desc": "Criteria not met", "score": 0},
                {"desc": "Divestment of council's investments", "score": 1},
                {"desc": "Divestment of pensions's investments", "score": 2},
            ],
        },
        "Gov&Fin Q11b": {
            "section": "Governance & Finance",
            "number": 11,
            "number_part": "b",
            "council_col": "Council",
            "score_col": "Score",
            "type": "select_one",
            "options": [
                {"desc": "Criteria not met", "score": 0},
                {"desc": "Partial divestment", "score": 1},
                {"desc": "All Fossil fuels divestment", "score": 2},
            ],
        },
        "Gov&Fin Q4": {
            "section": "Governance & Finance",
            "number": 4,
            "header_row": 5,
            "weighted": 3,
            "gss_col": "Local Authority Code",
            "score_col": "Score",
            "skip_check": {"col": "Calendar Year", "val": 2019},
            "type": "select_one",
            "options": [
                {"desc": "Criteria not met", "score": 0},
                {"desc": "2% or more emission reduction", "score": 1},
                {"desc": "5% or more emission reduction", "score": 2},
                {"desc": "10% or more emission reduction", "score": 3},
            ],
        },
        "EPC": {
            "section": "Buildings & Heating",
            "number": 7,
            "header_row": 1,
            "gss_col": "Local Authority Code",
            "score_col": "Tiered mark",
            "type": "select_one",
            "options": [
                {"desc": "Criteria not met", "score": 0},
                {"desc": "50% rated EPC C or above", "score": 1},
                {"desc": "60% rated EPC C or above", "score": 2},
                {"desc": "90% rated EPC C or above", "score": 3},
            ],
        },
    }

    def add_arguments(self, parser):
        parser.add_argument(
            "-q", "--quiet", action="store_true", help="Silence progress bars."
        )

    def add_options(self, q, details):
        if details.get("type", None) is not None:
            q_type = details["type"]
            if q_type == "yes_no":
                Option.objects.update_or_create(question=q, score=1, description="Yes")
                Option.objects.update_or_create(question=q, score=0, description="No")
            elif q_type == "select_one":
                for option in details["options"]:
                    Option.objects.update_or_create(
                        question=q, score=option["score"], description=option["desc"]
                    )

    def get_df(self, sheet, details):
        header_row = details.get("header_row", 0)
        df = pd.read_excel(
            self.question_file,
            sheet_name=sheet[0:31],
            header=header_row,
        )

        df = df.dropna(axis="index", how="all")

        return df

    def get_question(self, details):
        q = None
        try:
            args = {
                "section__title": details["section"],
                "number": details["number"],
            }
            if details.get("number_part", None) is not None:
                args["number_part"] = details["number_part"]

            q = Question.objects.get(**args)
        except Question.DoesNotExist:
            self.print_info("did not find question", 1)

        return q

    def get_score(self, q, row, details):
        q_type = details.get("type", "")
        score = row[details["score_col"]]

        if type(score) is str:
            match = re.match(r"\"?(\d) out of \d", score)
            if match:
                score = int(match.group(1))

        if q_type == "yes_no":
            if score == "Yes":
                score = 1
            else:
                score = 0

        return score

    def import_answers(self, user, rt, df, q, details):
        if details.get("gss_col", details.get("council_col", None)) is not None:
            for _, row in df.iterrows():
                if details.get("skip_check", None) is not None:
                    skip_check = details["skip_check"]
                    if row[skip_check["col"]] == skip_check["val"]:
                        continue

                council_col = details.get("gss_col", details.get("council_col", ""))

                value = row[council_col]
                args = {"name": value}
                if details.get("gss_col", None) is not None:
                    args = {"unique_id": value}
                try:
                    authority = PublicAuthority.objects.get(**args)
                except PublicAuthority.DoesNotExist:
                    # self.print_info("no authority found for ", args)
                    continue

                score = self.get_score(q, row, details)
                # self.print_info(authority.name, score)

                if not isinstance(score, numbers.Number) or math.isnan(score):
                    self.print_info(
                        f"score {score} is not a number {type(score)} for {authority.name}",
                        1,
                    )
                    continue

                if details.get("weighted", False):
                    orig_score = score
                    score = int(score * details["weighted"])
                    self.print_info(
                        f"weighted score is {score}, was {orig_score}, weighting is {details['weighted']}"
                    )

                option = None
                try:
                    option = Option.objects.get(question=q, score=score)
                except Option.DoesNotExist:
                    self.print_info(
                        f"No option found for {q.number}, {score}, {authority.name}", 1
                    )
                except Option.MultipleObjectsReturned:
                    self.print_info(
                        f"Multiple options returned for score {q.number}, {score}", 1
                    )
                except ValueError:
                    self.print_info(f"Bad score: {score}", 1)

                if option is None:
                    continue

                if not self.quiet:
                    self.print_info(option)

                r, _ = Response.objects.update_or_create(
                    question=q,
                    authority=authority,
                    user=user,
                    response_type=rt,
                    defaults={"option": option},
                )

    def print_info(self, message, level=2):
        if self.quiet and level > 1:
            return

        print(message)

    def handle(self, quiet: bool = False, *args, **kwargs):
        self.quiet = quiet
        user, _ = User.objects.get_or_create(username="National_Importer")
        rt = ResponseType.objects.get(type="Audit")
        for sheet, details in self.sheets.items():
            self.print_info("")
            self.print_info(
                "############################################################"
            )
            self.print_info(
                f"{details['section']}, {details['number']}, {details.get('number_part', '')}"
            )
            self.print_info("")
            df = self.get_df(sheet, details)
            q = self.get_question(details)
            self.add_options(q, details)
            self.import_answers(user, rt, df, q, details)
