import json
import math
import numbers
import re

from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

import pandas as pd

from crowdsourcer.models import (
    MarkingSession,
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

        parser.add_argument(
            "--add_options",
            action="store_true",
            help="Add options from the config",
        )

        parser.add_argument(
            "--session",
            action="store",
            required=True,
            help="Marking session to use questions with",
        )

        parser.add_argument(
            "--file",
            action="store",
            required=True,
            help="Excel file containing the national points",
        )

        parser.add_argument(
            "--config",
            action="store",
            required=True,
            help="JSON file containing the configuration for national points",
        )

        parser.add_argument(
            "--commit",
            action="store_true",
            help="Save the responses to the database",
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
        df = None
        try:
            df = pd.read_excel(
                self.question_file,
                sheet_name=sheet[0:31],
                header=header_row,
            )

            df = df.dropna(axis="index", how="all")
        except ValueError as e:
            self.print_info(
                f"{YELLOW}problem reading {sheet}: {e}{NOBOLD}",
                1,
            )

        return df

    def clear_existing_answers(self, q, details):
        if details.get("skip_clear_existing", None) is None:
            Response.objects.filter(question=q, response_type=self.rt).delete()

    def popuplate_council_lookup(self):
        lookup = {
            "local-authority-code": {},
            "official-name": {},
            "nice-name": {},
            "alt-names": {},
        }
        df = self.get_df("Council Names", {})
        if df is not None:
            df = df.rename(columns={df.columns[3]: "local-authority-code"})
            for _, row in df.iterrows():
                for col in ["local-authority-code", "official-name", "nice-name"]:
                    lookup[col][row[col]] = row["gss-code"]
                for name in row["alt-names"].split(","):
                    name = name.strip().lower()
                    lookup["alt-names"][name] = row["gss-code"]
        else:
            self.print_info(
                f"{YELLOW}No council names tab found so not populating council lookup{NOBOLD}",
                1,
            )

        self.council_lookup = lookup

    def get_gss_code_for_council(self, council):
        gss = None
        if not isinstance(council, str):
            return None
        council = council.strip()
        subs = (
            (r" UA$", ""),
            (r" LB$", ""),
            (r" CC$", " County Council"),
            (r" BC$", " Borough Council"),
            (r" MD$", ""),
        )
        for s in subs:
            council = re.sub(s[0], s[1], council)

        for lookup in [
            "local-authority-code",
            "official-name",
            "nice-name",
            "alt-names",
        ]:
            if self.council_lookup[lookup].get(council):
                gss = self.council_lookup[lookup][council]
                break
            if self.council_lookup[lookup].get(council.lower()):
                gss = self.council_lookup[lookup][council.lower()]
                break

        return gss

    def get_question(self, details):
        q = None
        try:
            args = {
                "section__title": details["section"],
                "section__marking_session": self.session,
                "number": details["number"],
            }
            if details.get("number_part", None) is not None:
                args["number_part"] = details["number_part"]

            q = Question.objects.get(**args)
        except Question.DoesNotExist:
            self.print_info("did not find question", 1)

        return q

    def get_points_map_conf(self, authority, config):
        points_map = config["points_map"]
        if config.get("points_map_option"):
            c = config["points_map_option"]
            q_score = Response.get_response_for_question(
                session=self.session,
                section=c["section"],
                question_number=c["question_number"],
                response_type="Audit",
                authority=authority.name,
            )
            if q_score == c["response"]:
                points_map = c["map"]

        return points_map

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
            if score == "No Penalty Mark":
                score = 0

        if details.get("negative", False):
            if score != 0:
                desc = score
                if type(score) is str and score.find("-") == -1:
                    desc = f"-{score}"
                points_map_conf = self.get_points_map_conf(authority, details)
                points_map = points_map_conf.get(
                    authority.country,
                    points_map_conf.get(authority.type, points_map_conf["default"]),
                )
                try:
                    score = points_map[f"{desc}"]
                except KeyError:
                    self.print_info(f"{RED}bad negative points desc: {desc}{NOBOLD}", 1)
                    desc = "None"
                if details["type"] == "yes_no":
                    desc = "Yes"
            else:
                if details["type"] == "yes_no":
                    desc = "No"
                else:
                    desc = "No Penalty Mark"
        elif q_type == "yes_no":
            if score == "Yes" or score == "1" or score == 1:
                desc = "Yes"
                score = 1
            else:
                score = 0
                desc = "Evidence doesn't meet criteria"
        else:
            desc = None
            if details.get("options"):
                for opt in details["options"]:
                    if opt["score"] == score:
                        desc = opt["desc"]
                        break
                    if opt["desc"] == score:
                        desc = score
                        score = opt["score"]
                        break

        return desc, score

    def import_answers(self, user, rt, df, q, details):
        count = 0
        auto_zero = 0
        bad_authority_count = 0
        if details.get("gss_col", details.get("council_col", None)) is not None:
            for i, row in df.iterrows():
                if details.get("skip_check", None) is not None:
                    skip_check = details["skip_check"]
                    if (
                        skip_check.get("unless_match")
                        and row[skip_check["col"]] != skip_check["val"]
                    ):
                        continue
                    elif (
                        not skip_check.get("unless_match")
                        and row[skip_check["col"]] == skip_check["val"]
                    ):
                        continue

                gss_col = details.get("gss_col", "Local Authority Code")
                if row.get(gss_col) and not pd.isna(row.get(gss_col)):
                    gss = row[gss_col]
                    code = gss
                else:
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
                        and row.get("manually added local-authority-code", None)
                        is not None
                    ) and not pd.isna(row["manually added local-authority-code"]):
                        code = row["manually added local-authority-code"]

                    gss = self.get_gss_code_for_council(code)

                args = None
                if gss is None:
                    value = None
                    try:
                        value = row[council_col]
                    except KeyError:
                        self.print_info(
                            f"{RED}no council column found {council_col}{NOBOLD}", 1
                        )

                    if value:
                        gss = self.get_gss_code_for_council(value)
                        if gss is not None:
                            args = {"unique_id": gss}
                        else:
                            args = {"name": value}
                            if details.get("gss_col", None) is not None:
                                args = {"unique_id": value}
                else:
                    args = {"unique_id": gss}

                if args is None:
                    self.print_info(
                        f"{RED}could not work out council args for line {i}{NOBOLD}", 1
                    )
                    continue

                try:
                    authority = PublicAuthority.objects.get(**args)
                except PublicAuthority.DoesNotExist:
                    bad_authority_count += 1
                    self.print_info(
                        f"no authority found for code {code}, {args} on line {i}", 1
                    )
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
                        if score_desc is not None:
                            option = Option.objects.get(
                                question=q, description=score_desc
                            )
                        else:
                            option = Option.objects.get(question=q, score=score)
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

                if self.check_options_only:
                    count += 1
                    continue

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
                option = None
                try:
                    if type(default) is int:
                        option = Option.objects.get(question=q, score=default)
                    else:
                        option = Option.objects.get(question=q, description=default)
                except Option.DoesNotExist:
                    self.print_info(
                        f"{RED}No matching default response for {q.number}, {default}{NOBOLD}",
                        1,
                    )

                if option:
                    groups = q.questiongroup.all()
                    answered = Response.objects.filter(
                        response_type=rt, question=q
                    ).values("authority")
                    councils = PublicAuthority.objects.filter(
                        marking_session=self.session, questiongroup__in=groups
                    ).exclude(id__in=answered)
                    if details.get("missing_filter", None) is not None:
                        councils = councils.filter(**details["missing_filter"])

                    if self.check_options_only:
                        auto_zero = councils.count()
                    else:
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
        q_number_and_part = f"{details['number']}{details.get('number_part', '')}"
        if (
            not self.completed.get(details["section"])
            or q_number_and_part not in self.completed[details["section"]]
        ):
            self.print_info(
                f"{YELLOW}not marked complete so skipping {details['section']}, {details['number']}, {details.get('number_part', '')}{NOBOLD}",
                1,
            )
            return

        df = self.get_df(sheet, details)
        if df is None:
            return

        q = self.get_question(details)
        if q is None:
            self.print_info(
                f"{RED}Could not find questions {details['section']}, {details['number']}, {details.get('number_part', '')}{NOBOLD}",
                1,
            )
            return

        self.clear_existing_answers(q, details)
        if self.add_options:
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
        commit: bool = False,
        *args,
        **kwargs,
    ):
        self.quiet = quiet

        self.check_options_only = not commit
        self.question_file = settings.BASE_DIR / "data" / kwargs["file"]
        self.config_file = settings.BASE_DIR / "data" / kwargs["config"]

        with open(self.config_file) as conf_file:
            config = json.load(conf_file)

        self.completed = config.get("completed", {})
        self.sheets = config["sheets"]
        self.ca_sheets = config["ca_sheets"]

        self.popuplate_council_lookup()
        user, _ = User.objects.get_or_create(username="National_Importer")
        self.rt = ResponseType.objects.get(type="Audit")
        self.session = MarkingSession.objects.get(label=kwargs["session"])
        self.add_options = kwargs["add_options"]

        if self.check_options_only:
            self.print_info(
                f"{YELLOW}Not saving any responses, run with --commit to do so{NOBOLD}",
                1,
            )

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

        if self.check_options_only:
            self.print_info(
                f"{YELLOW}Not saving any responses, run with --commit to do so{NOBOLD}",
                1,
            )
