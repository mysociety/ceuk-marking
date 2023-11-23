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

YELLOW = "\033[33m"
RED = "\033[31m"
GREEN = "\033[32m"
NOBOLD = "\033[0m"


class Command(BaseCommand):
    help = "import questions"

    question_file = settings.BASE_DIR / "data" / "national_data.xlsx"

    sheets = [
        {
            "sheet": "Copy of Planning Q10B (pivot ta",
            "section": "Planning & Land Use",
            "number": 10,
            "number_part": "b",
            "default_if_missing": 0,
            "gss_col": "local-authority-code",
            "score_col": "Unweighted section score",
            "evidence_link": """https://data.barbour-abi.com/smart-map/repd/beis/?type=repd
https://data.barbour-abi.com/smart-map/repd/desnz/?type=heat_network""",
            "type": "select_one",
            "options": [
                {"desc": "Criteria not met", "score": 0},
                {"desc": "1 renewable energy system", "score": 1},
                {"desc": "2 renewable energy systems", "score": 2},
                {"desc": "3 renewable energy systems", "score": 3},
                {"desc": "4 renewable energy systems", "score": 4},
                {"desc": "5 renewable energy systems", "score": 5},
            ],
        },
        # XXX - negative points
        {
            "sheet": "Planning Q11 Fossil Fuel infras",
            "section": "Planning & Land Use",
            "number": 11,
            "default_if_missing": "No",
            "missing_filter": {"type__in": ["CTY", "UTA"]},
            "evidence": "Link to Evidence",
            "evidence_detail": "Status (explanation)",
            "negative": True,
            "gss_col": "local authority code",
            "score_col": "Score",
            "type": "yes_no",
            "points_map": {
                "default": {
                    "-20%": -4.4,
                    "-0.2": -4.4,
                    "-6.0": -4.4,
                },
            },
        },
        {
            "sheet": "Recycling",
            "section": "Waste Reduction & Food",
            "number": 8,
            "header_row": 6,
            "council_col": "Local Authority 2020/21",
            "score_col": "Mark",
            "evidence": "Evidence",
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
        {
            "sheet": "Residual Waste",
            "section": "Waste Reduction & Food",
            "number": 9,
            "header_row": 6,
            "council_col": "Local Authority 2020/21",
            "score_col": "Mark",
            "evidence": "Source",
            # XXX - tiered
            "type": "select_one",
            "options": [
                {"desc": "Criteria not met", "score": 0},
                {"desc": "300-400kg residual waste per household", "score": 1},
                {"desc": "Less than 300kg residual waste per household", "score": 2},
            ],
        },
        {
            "sheet": "Transport Q4 - 20mph",
            "section": "Transport",
            "number": 4,
            "council_col": "Council name",
            "score_col": "Award point - only 1 tier",
            "evidence": "Evidence link",
            "default_if_missing": 0,
            "missing_filter": {"type__in": ["CTY", "UTA"], "country": "england"},
            "type": "yes_no",
        },
        {
            "sheet": "Transport Q6 - Active Travel England scores",
            "section": "Transport",
            "number": 6,
            "header_row": 1,
            "council_col": "Local Authority",
            "score_col": "Unweighted scores",
            "evidence": "Evidence link",
            "type": "select_one",
            "options": [
                {"desc": "Criteria not met", "score": 0},
                {"desc": "Active Travel Capability Rating - 1", "score": 1},
                {"desc": "Active Travel Capability Rating - 2", "score": 2},
                {"desc": "Active Travel Capability Rating - 3", "score": 3},
                {"desc": "Active Travel Capability Rating - 4", "score": 4},
            ],
        },
        {
            "sheet": "Transport 8B - Bus Ridership",
            "section": "Transport",
            "number": 8,
            "number_part": "b",
            "header_row": 2,
            "council_col": "Local Authority",
            "score_col": "Unweighted Question scores",
            "evidence": "Evidence link",
            "type": "select_one",
            "options": [
                {"desc": "Criteria not met", "score": 0},
                {"desc": "75 journeys per head of population", "score": 1},
                {"desc": "150 journeys per head of population", "score": 2},
            ],
        },
        {
            "sheet": "Transport 10 - EV chargers",
            "section": "Transport",
            "number": 10,
            "header_row": 1,
            "council_col": "Local Authority / Region Name",
            "score_col": "Unweighted Question Scores",
            "evidence": "Evidence link",
            "type": "select_one",
            "options": [
                {"desc": "Criteria not met", "score": 0},
                {
                    "desc": "60+ chargers per 100,000 people (but less than 434 per 100k)",
                    "score": 1,
                },
                {
                    "desc": "434+ chargers per 100,000 people",
                    "score": 2,
                },
            ],
        },
        # XXX - negative points
        {
            "sheet": "Transport 12a - Air Quality NO2",
            "section": "Transport",
            "number": 12,
            "number_part": "a",
            "header_row": 1,
            "council_col": "Local authority name",
            "score_col": "Award negative points",
            "negative": True,
            "type": "select_one",
            "evidence_link": "https://policy.friendsoftheearth.uk/insight/which-neighbourhoods-have-worst-air-pollution",
            "options": [
                {
                    "desc": "None",
                    "score": 0,
                },
                {
                    "desc": "-2%",
                    "score": 0,
                },
                {
                    "desc": "-6%",
                    "score": 0,
                },
            ],
            "points_map": {
                "UTA": {
                    "-2%": -0.5,
                    "-6%": -1.5,
                },
                "MTD": {
                    "-2%": -0.5,
                    "-6%": -1.5,
                },
                "LBO": {
                    "-2%": -0.5,
                    "-6%": -1.5,
                },
                "CTY": {
                    "-2%": -0.5,
                    "-6%": -1.5,
                },
                "default": {
                    "-2%": -0.16,
                    "-6%": -0.48,
                },
            },
        },
        # XXX - negative points
        {
            "sheet": "Transport 12b - Air Quality PM2.5",
            "section": "Transport",
            "number": 12,
            "number_part": "b",
            "header_row": 1,
            "council_col": "Local authority name",
            "score_col": "Award negative points",
            "negative": True,
            "type": "select_one",
            "evidence_link": "https://policy.friendsoftheearth.uk/insight/which-neighbourhoods-have-worst-air-pollution",
            "options": [
                {
                    "desc": "None",
                    "score": 0,
                },
                {
                    "desc": "-2%",
                    "score": 0,
                },
                {
                    "desc": "-4%",
                    "score": 0,
                },
            ],
            "points_map": {
                "UTA": {
                    "-2%": -0.5,
                    "-4%": -1,
                },
                "MTD": {
                    "-2%": -0.5,
                    "-4%": -1,
                },
                "LBO": {
                    "-2%": -0.5,
                    "-4%": -1,
                },
                "CTY": {
                    "-2%": -0.5,
                    "-4%": -1,
                },
                "default": {
                    "-2%": -0.16,
                    "-4%": -0.32,
                },
            },
        },
        {
            "sheet": "Transport Q11 (negative)",
            "section": "Transport",
            "number": 11,
            "number_part": None,
            "council_col": "authority",
            "score_col": "score",
            "negative": True,
            "skip_clear_existing": False,
            "update_points_only": True,
            "type": "multi_select",
            "points_map": {
                "UTA": {
                    "-": 0,
                    "-0.05": -1.25,
                    "-0.15": -3.75,
                    "-0.2": -5,
                },
                "LBO": {
                    "-": 0,
                    "-0.05": -1.25,
                    "-0.15": -3.75,
                    "-0.2": -5,
                },
                "MTD": {
                    "-": 0,
                    "-0.05": -1.25,
                    "-0.15": -3.75,
                    "-0.2": -5,
                },
                "CTY": {
                    "-": 0,
                    "-0.05": -1.25,
                    "-0.15": -3.75,
                    "-0.2": -5,
                },
                "default": {
                    "-": 0,
                    "-0.05": -0.4,
                    "-0.15": -1.2,
                    "-0.2": -1.6,
                },
            },
        },
        {
            "sheet": "Biodiversity Q2 - Pesticides",
            "section": "Biodiversity",
            "number": 2,
            "header_row": 1,
            "council_col": "Council",
            "score_col": "Unweighted points",
            "default_if_missing": 0,
            "evidence": "Link to data",
            "evidence_detail": "Banned Pesticides?",
            "type": "yes_no",
        },
        {
            "sheet": "Biodiversity Q4 - Wildlife Sites ",
            "section": "Biodiversity",
            "number": 4,
            "header_row": 2,
            "council_col": "Council",
            "score_col": "Point awarded",
            "evidence": "Evidence link",
            "type": "yes_no",
        },
        {
            "sheet": "Sheet23",
            "section": "Biodiversity",
            "number": 7,
            "council_col": "local authority council code",
            "score_col": "Unweighted score",
            "type": "select_one",
            "default_if_missing": 0,
            "evidence": "Evidence link",
            "options": [
                {"desc": "Criteria not met", "score": 0},
                {"desc": "1-3 Green Flag accredited parks", "score": 1},
                {"desc": "4+ Green Flag accredited parks", "score": 2},
            ],
        },
        {
            "sheet": "Gov&Fin Q11a",
            "section": "Governance & Finance",
            "number": 11,
            "number_part": "a",
            "council_col": "Council",
            "score_col": "Score",
            "evidence": "Evidence",
            "default_if_missing": 0,
            "type": "select_one",
            "options": [
                {"desc": "Criteria not met", "score": 0},
                {"desc": "Divestment of council's investments", "score": 1},
                {"desc": "Divestment of pensions's investments", "score": 2},
            ],
        },
        {
            "sheet": "Gov&Fin Q11b",
            "section": "Governance & Finance",
            "number": 11,
            "number_part": "b",
            "council_col": "Council",
            "score_col": "Score",
            "evidence": "Evidence",
            "default_if_missing": 0,
            "type": "select_one",
            "options": [
                {"desc": "Criteria not met", "score": 0},
                {"desc": "Partial divestment", "score": 1},
                {"desc": "All Fossil fuels divestment", "score": 2},
            ],
        },
        {
            "sheet": "Gov&Fin Q4",
            "section": "Governance & Finance",
            "number": 4,
            "header_row": 6,
            "gss_col": "Local Authority Code",
            "score_col": "Score",
            "skip_check": {"col": "Calendar Year", "val": 2019},
            "evidence_link": "https://www.gov.uk/government/statistics/uk-local-authority-and-regional-greenhouse-gas-emissions-national-statistics-2005-to-2021",
            "type": "select_one",
            "options": [
                {"desc": "Criteria not met", "score": 0},
                {"desc": "2% or more emission reduction", "score": 1},
                {"desc": "5% or more emission reduction", "score": 2},
                {"desc": "10% or more emission reduction", "score": 3},
            ],
        },
        {
            "sheet": "Gov&Fin Q5 CA",
            "section": "Governance & Finance (CA)",
            "number": 5,
            "header_row": 6,
            "gss_col": "local-authority-code",
            "evidence_link": "https://docs.google.com/spreadsheets/d/1dnoEk-l6TJDZfdrfVbkeMBQmj9dPVAQxuULPrNG5uXY/edit#gid=1108346321",
            "score_col": "Score",
            "type": "select_one",
            "options": [
                {"desc": "Criteria not met", "score": 0},
                {"desc": "2% or more emission reduction", "score": 1},
                {"desc": "5% or more emission reduction", "score": 2},
                {"desc": "10% or more emission reduction", "score": 3},
            ],
        },
        {
            "sheet": "Gov&Fin Q8",
            "section": "Governance & Finance",
            "number": 8,
            "gss_col": "local-authority-code",
            "score_col": "Score",
            "type": "select_one",
            "skip_clear_existing": False,
            "options": [
                {"desc": "Criteria not met", "score": 0},
                {"desc": "more than 0.5% of staff working on climate", "score": 1},
                {"desc": "more than 1% of staff working on climate", "score": 2},
                {"desc": "more than 2% of staff working on climate", "score": 3},
            ],
        },
        {
            "sheet": "Gov&Fin Q8 CA",
            "section": "Governance & Finance (CA)",
            "number": 9,
            "header_row": 1,
            "gss_col": "local-authority-code",
            "score_col": "Score",
            "type": "select_one",
            "skip_clear_existing": False,
            "options": [
                {"desc": "Criteria not met", "score": 0},
                {"desc": "more than 0.5% of staff working on climate", "score": 1},
                {"desc": "more than 1% of staff working on climate", "score": 2},
                {"desc": "more than 2% of staff working on climate", "score": 3},
            ],
        },
        {
            "sheet": "Gov&Fin Q12 (negative)",
            "section": "Governance & Finance",
            "number": 12,
            "number_part": None,
            "negative": True,
            "gss_col": "local-authority-code",
            "score_col": "score",
            "type": "yes_no",
            "update_points_only": True,
            "skip_clear_existing": False,
            "update": True,
            "points_map": {
                "default": {
                    "-15": -4.35,
                    "-0.15": -4.35,
                },
            },
        },
        {
            "sheet": "EPC - England & Wales",
            "section": "Buildings & Heating",
            "number": 7,
            "header_row": 5,
            "gss_col": "Local Authority Code",
            "score_col": "Tiered mark",
            "evidence": "Evidence",
            "type": "select_one",
            "options": [
                {"desc": "Criteria not met", "score": 0},
                {"desc": "50% rated EPC C or above", "score": 1},
                {"desc": "60% rated EPC C or above", "score": 2},
                {"desc": "90% rated EPC C or above", "score": 3},
            ],
        },
        {
            "sheet": "EPC - Scotland",
            "section": "Buildings & Heating",
            "number": 7,
            "header_row": 5,
            "council_col": "Local authority",
            "score_col": "Tiered mark",
            "evidence": "Evidence",
            "type": "select_one",
            "skip_clear_existing": True,
            "options": [
                {"desc": "Criteria not met", "score": 0},
                {"desc": "50% rated EPC C or above", "score": 1},
                {"desc": "60% rated EPC C or above", "score": 2},
                {"desc": "90% rated EPC C or above", "score": 3},
            ],
        },
        {
            "sheet": "EPC - NI",
            "section": "Buildings & Heating",
            "number": 7,
            "header_row": 2,
            "gss_col": "Northern Irish Council GSS code",
            "score_col": "Tiered mark",
            "evidence": "Evidence",
            "type": "select_one",
            "skip_clear_existing": True,
            "options": [
                {"desc": "Criteria not met", "score": 0},
                {"desc": "50% rated EPC C or above", "score": 1},
                {"desc": "60% rated EPC C or above", "score": 2},
                {"desc": "90% rated EPC C or above", "score": 3},
            ],
        },
        {
            "sheet": "Collab & Engagement Q11",
            "section": "Collaboration & Engagement",
            "number": 11,
            "header_row": 1,
            "council_col": "Council",
            "score_col": "Unweighted Points",
            "evidence": "Evidence link",
            "type": "select_one",
            "default_if_missing": 0,
            "options": [
                {"desc": "None", "score": 0},
                {
                    "desc": "Passed a fossil advertising motion or amended existing policy",
                    "score": 1,
                },
            ],
        },
    ]

    ca_sheets = [
        {
            "sheet": "Gov&Fin Q11a",
            "section": "Governance & Finance (CA)",
            "number": 12,
            "number_part": "a",
            "council_col": "Council",
            "score_col": "Score",
            "type": "select_one",
            "evidence": "Evidence",
            "default_if_missing": 0,
            "options": [
                {"desc": "Criteria not met", "score": 0},
                {"desc": "Divestment of council's investments", "score": 1},
                {"desc": "Divestment of pensions's investments", "score": 2},
            ],
        },
        {
            "sheet": "Gov&Fin Q11b",
            "section": "Governance & Finance (CA)",
            "number": 12,
            "number_part": "b",
            "council_col": "Council",
            "score_col": "Score",
            "evidence": "Evidence",
            "default_if_missing": 0,
            "type": "select_one",
            "options": [
                {"desc": "Criteria not met", "score": 0},
                {"desc": "Partial divestment", "score": 1},
                {"desc": "All Fossil fuels divestment", "score": 2},
            ],
        },
        {
            "sheet": "Transport Q6 - Active Travel England scores",
            "section": "Transport (CA)",
            "number": 7,
            "header_row": 1,
            "council_col": "Local Authority",
            "score_col": "Unweighted scores",
            "evidence": "Evidence link",
            "type": "select_one",
            "options": [
                {"desc": "Criteria not met", "score": 0},
                {"desc": "Active Travel Capability Rating - 1", "score": 1},
                {"desc": "Active Travel Capability Rating - 2", "score": 2},
                {"desc": "Active Travel Capability Rating - 3", "score": 3},
                {"desc": "Active Travel Capability Rating - 4", "score": 4},
            ],
        },
        {
            "sheet": "Transport 8B - Bus Ridership",
            "section": "Transport (CA)",
            "number": 4,
            "number_part": "b",
            "header_row": 2,
            "council_col": "Local Authority",
            "score_col": "Unweighted Question scores",
            "evidence": "Evidence link",
            "type": "select_one",
            "default_if_missing": 0,
            "options": [
                {"desc": "Criteria not met", "score": 0},
                {"desc": "75 journeys per head of population", "score": 1},
                {"desc": "150 journeys per head of population", "score": 2},
            ],
        },
        {
            "sheet": "Transport 10 - EV chargers",
            "section": "Transport (CA)",
            "number": 8,
            "header_row": 1,
            "council_col": "Local Authority / Region Name",
            "score_col": "Unweighted Question Scores",
            "evidence": "Evidence link",
            "type": "select_one",
            "default_if_missing": 0,
            "options": [
                {"desc": "Criteria not met", "score": 0},
                {
                    "desc": "60+ chargers per 100,000 people (but less than 434 per 100k)",
                    "score": 1,
                },
                {
                    "desc": "434+ chargers per 100,000 people",
                    "score": 2,
                },
            ],
        },
        {
            "sheet": "Transport 1b CA (negative)",
            "section": "Transport (CA)",
            "number": 1,
            "number_part": "b",
            "council_col": "authority",
            "score_col": "score",
            "negative": True,
            "update_points_only": True,
            "skip_clear_existing": False,
            "type": "select_one",
            "evidence": "Evidence",
            "options": [
                {
                    "desc": "None",
                    "score": 0,
                },
                {
                    "desc": "-5%",
                    "score": 0,
                },
                {
                    "desc": "-20%",
                    "score": 0,
                },
            ],
            "points_map": {
                "default": {
                    "-0.05": -1.05,
                    "-0.2": -3.15,
                },
            },
        },
        {
            "sheet": "Collab & Engagement Q11",
            "section": "Collaboration & Engagement (CA)",
            "number": 9,
            "header_row": 1,
            "council_col": "Council",
            "score_col": "Unweighted Points",
            "evidence": "Evidence link",
            "type": "select_one",
            "default_if_missing": 0,
            "options": [
                {"desc": "None", "score": 0},
                {
                    "desc": "Passed a fossil advertising motion or amended existing policy",
                    "score": 1,
                },
            ],
        },
    ]

    def add_arguments(self, parser):
        parser.add_argument(
            "-q", "--quiet", action="store_true", help="Silence debug data."
        )
        parser.add_argument("--only_sheet", help="only process this sheet")
        parser.add_argument(
            "--negative_only",
            action="store_true",
            help="only process Qs with negative points",
        )

    def add_options(self, q, details):
        if details.get("type", None) is not None:
            expected_options = 2
            q_type = details["type"]
            if q_type == "yes_no":
                Option.objects.update_or_create(question=q, score=1, description="Yes")
                Option.objects.update_or_create(question=q, score=0, description="No")
            elif q_type == "select_one":
                expected_options = len(details["options"])
                for option in details["options"]:
                    Option.objects.update_or_create(
                        question=q, score=option["score"], description=option["desc"]
                    )

            option_count = Option.objects.filter(question=q).count()
            if option_count != expected_options:
                self.print_info(
                    f"{YELLOW}Unexpected option count for {q.section.title} {q.number_and_part} - {expected_options} expected, {option_count} found{NOBOLD}",
                    1,
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

    def clear_existing_answers(self, q, details):
        if details.get("skip_clear_existing", None) is None:
            Response.objects.filter(question=q, response_type=self.rt).delete()

    def popuplate_council_lookup(self):
        df = self.get_df("council names", {})
        lookup = {}
        for _, row in df.iterrows():
            lookup[row["local-authority-code"]] = row["gss-code"]

        self.council_lookup = lookup

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

    def get_score(self, q, row, details, authority):
        q_type = details.get("type", "")
        score = row[details["score_col"]]

        if type(score) is str:
            match = re.match(r"\"?(\d) out of \d", score)
            if match:
                score = int(match.group(1))
            match = re.match(r".*-(\d%).*", score)
            if match:
                score = match.group(1)

        if details.get("negative", False):
            if score != 0:
                desc = score
                if type(score) is str and score.find("-") == -1:
                    desc = f"-{score}"
                points_map = details["points_map"].get(
                    authority.type, details["points_map"]["default"]
                )
                score = points_map[f"{desc}"]
                if details["type"] == "yes_no":
                    desc = "Yes"
            else:
                if details["type"] == "yes_no":
                    desc = "No"
                else:
                    desc = "None"
        elif q_type == "yes_no":
            if score == "Yes" or score == "1" or score == 1:
                desc = "Yes"
                score = 1
            else:
                score = 0
                desc = "No"
        else:
            for opt in details["options"]:
                if opt["score"] == score:
                    desc = opt["desc"]
                    break

        return desc, score

    def import_answers(self, user, rt, df, q, details):
        count = 0
        auto_zero = 0
        bad_authority_count = 0
        if details.get("gss_col", details.get("council_col", None)) is not None:
            for _, row in df.iterrows():
                if details.get("skip_check", None) is not None:
                    skip_check = details["skip_check"]
                    if row[skip_check["col"]] == skip_check["val"]:
                        continue

                council_col = details.get("gss_col", details.get("council_col", ""))

                code = row.get(
                    "local authority code",
                    row.get(
                        "local authority council code",
                        row.get(
                            "Local authority council code",
                            row.get("local-authority-code", ""),
                        ),
                    ),
                )

                if (
                    (code == "" or pd.isna(code))
                    and row.get("manually added local-authority-code", None) is not None
                ) and not pd.isna(row["manually added local-authority-code"]):
                    code = row["manually added local-authority-code"]

                gss = self.council_lookup.get(
                    code,
                    None,
                )

                if gss is None:
                    value = row[council_col]
                    args = {"name": value}
                    if details.get("gss_col", None) is not None:
                        args = {"unique_id": value}
                else:
                    args = {"unique_id": gss}

                try:
                    authority = PublicAuthority.objects.get(**args)
                except PublicAuthority.DoesNotExist:
                    bad_authority_count += 1
                    self.print_info(f"no authority found for code {code}, {args}", 1)
                    continue

                # doing it this way prevents a lot of annoying output from the above
                # for sheets that do CA and non CA councils
                if authority.questiongroup not in q.questiongroup.all():
                    continue

                score_desc, score = self.get_score(q, row, details, authority)
                # self.print_info(f"{authority.name}, {score_desc}, {score}", 1)

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
                if not details.get("update_points_only", False):
                    try:
                        option = Option.objects.get(question=q, description=score_desc)
                    except Option.DoesNotExist:
                        self.print_info(
                            f"No option found for {q.number}, {score_desc}, {authority.name}",
                            1,
                        )
                    except Option.MultipleObjectsReturned:
                        self.print_info(
                            f"Multiple options returned for score {q.number}, {score_desc}",
                            1,
                        )
                    except ValueError:
                        self.print_info(f"Bad score: {score_desc}", 1)

                    if option is None:
                        continue

                    if not self.quiet:
                        self.print_info(f"{authority.name}: {option}")

                if details.get("update_points_only", False):
                    try:
                        r = Response.objects.get(
                            question=q,
                            authority=authority,
                            response_type=rt,
                        )
                    except Response.DoesNotExist:
                        self.print_info(
                            f"{YELLOW}No matching response for {q.number}, {authority.name}{NOBOLD}",
                            1,
                        )
                        continue
                else:
                    r, _ = Response.objects.update_or_create(
                        question=q,
                        authority=authority,
                        user=user,
                        response_type=rt,
                        defaults={"option": option},
                    )
                    if score != 0 and details.get("evidence", None) is not None:
                        r.public_notes = row[details["evidence"]]
                        r.page_number = 0
                        r.save()

                    if score != 0 and details.get("evidence_link", None) is not None:
                        r.public_notes = details["evidence_link"]
                        r.page_number = 0
                        r.save()

                    if score != 0 and details.get("evidence_detail", None) is not None:
                        r.evidence = row[details["evidence_detail"]]
                        r.save()

                    if score != 0 and details.get("evidence_text", None) is not None:
                        r.evidence = details["evidence_text"]
                        r.save()

                if details.get("negative", False):
                    r.points = score
                    r.save()

                count += 1
            if details.get("default_if_missing", None) is not None:
                default = details["default_if_missing"]
                if type(default) is int:
                    option = Option.objects.get(question=q, score=default)
                else:
                    option = Option.objects.get(question=q, description=default)
                groups = q.questiongroup.all()
                answered = Response.objects.filter(response_type=rt, question=q).values(
                    "authority"
                )
                councils = PublicAuthority.objects.filter(
                    questiongroup__in=groups
                ).exclude(id__in=answered)
                if details.get("missing_filter", None) is not None:
                    councils = councils.filter(**details["missing_filter"])

                for council in councils:
                    r, _ = Response.objects.update_or_create(
                        question=q,
                        authority=council,
                        user=user,
                        response_type=rt,
                        defaults={"option": option},
                    )
                    auto_zero += 1

        message = f"{GREEN}Added {count} responses, {auto_zero} default 0 responses, bad authorities {bad_authority_count}{NOBOLD}"

        if count == 0:
            message = f"{YELLOW}{message}{NOBOLD}"
        self.print_info(message, 1)

    def handle_sheet(self, sheet, details, user):
        self.print_info("")
        self.print_info("--", 1)
        self.print_info(sheet, 1)
        self.print_info(
            f"{details['section']}, {details['number']}, {details.get('number_part', '')}",
            1,
        )
        self.print_info("")
        df = self.get_df(sheet, details)
        q = self.get_question(details)
        if q is None:
            self.print_info(
                f"{RED}Could not find questions {details['section']}, {details['number']}, {details.get('number_part', '')}{NOBOLD}",
                1,
            )
            return

        self.clear_existing_answers(q, details)
        self.add_options(q, details)
        self.import_answers(user, self.rt, df, q, details)

    def print_info(self, message, level=2):
        if self.quiet and level > 1:
            return

        print(message)

    def handle(
        self,
        quiet: bool = False,
        only_sheet: str = None,
        negative_only: bool = False,
        *args,
        **kwargs,
    ):
        self.quiet = quiet

        self.popuplate_council_lookup()
        user, _ = User.objects.get_or_create(username="National_Importer")
        self.rt = ResponseType.objects.get(type="Audit")
        for details in self.sheets:
            sheet = details["sheet"]
            if only_sheet is not None and sheet != only_sheet:
                continue

            if negative_only and not details.get("negative", False):
                continue

            self.handle_sheet(sheet, details, user)

        for details in self.ca_sheets:
            sheet = details["sheet"]
            if only_sheet is not None and sheet != only_sheet:
                continue

            if negative_only and not details.get("negative", False):
                continue

            self.handle_sheet(sheet, details, user)
