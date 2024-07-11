from collections import defaultdict

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
    help = "Add automatic points"

    def add_arguments(self, parser):
        parser.add_argument(
            "-q", "--quiet", action="store_true", help="Silence debug text."
        )

        parser.add_argument(
            "--session",
            action="store",
            required=True,
            help="Marking session to use questions with",
        )

        parser.add_argument(
            "--previous",
            action="store",
            required=True,
            help="Previous marking session to copy answers from",
        )

        parser.add_argument(
            "--file",
            action="store",
            required=True,
            help="CSV file containing the automatic points",
        )

        parser.add_argument(
            "--option_map",
            action="store",
            help="CSV file containing option mapping from previous answers",
        )
        parser.add_argument(
            "--stage",
            action="store",
            required=True,
            help="marking stage to add responses to",
        )

        parser.add_argument(
            "--update_existing_responses",
            action="store_true",
            help="Always update existings responses",
        )

        parser.add_argument(
            "--commit", action="store_true", help="Commits changes to DB"
        )

    def print_info(self, message, level=2):
        if self.quiet and level > 1:
            return

        self.stdout.write(message)

    def get_points(self, file):
        df = pd.read_csv(file)
        df["answer in GRACE"] = df["answer in GRACE"].astype(str)

        return df

    def get_option_map(self, file):
        if file == "" or file is None:
            return {}

        df = pd.read_csv(file)
        df.question = df.question.astype(str)

        option_map = defaultdict(dict)
        for _, option in df.iterrows():
            if option_map[option["section"]].get(option["question"]) is None:
                option_map[option["section"]][option["question"]] = {}

            option_map[option["section"]][option["question"]][option["prev_option"]] = (
                option["new_option"]
            )

        return option_map

    def scrub_council_type(self, types):
        type_map = {
            "COMB": "COMB",
            "CTY": "CTY",
            "LGD": "LGD",
            "MD": "MTD",
            "MTD": "MTD",
            "UTA": "UTA",
            "COI": "COI",
            "NMD": "NMD",
            "DIS": "DIS",
            "CC": "LBO",
            "LBO": "LBO",
            "SCO": "UTA",
            "WPA": "UTA",
            "NID": "UTA",
            "UA": "UTA",
            "SRA": "COMB",
        }
        scrubbed = []
        for t in types:
            t = t.strip()
            if type_map.get(t) is not None:
                scrubbed.append(type_map[t])
            else:
                self.print_info(f"bad council type {t}", 1)
        return scrubbed

    def get_mapped_answer(self, answer, q, answer_map):
        if (
            answer_map.get(q.section.title) is not None
            and answer_map[q.section.title].get(q.number_and_part) is not None
            and answer_map[q.section.title][q.number_and_part].get(answer) is not None
        ):
            return answer_map[q.section.title][q.number_and_part][answer]

        return answer

    def handle(
        self,
        quiet: bool = False,
        commit: bool = False,
        file: str = "",
        stage: str = "",
        session: str = "",
        option_map: str = "",
        update_existing_responses: bool = False,
        *args,
        **kwargs,
    ):
        self.quiet = quiet

        u, _ = User.objects.get_or_create(
            username="Auto_point_script",
        )

        try:
            rt = ResponseType.objects.get(type=stage)
            prev_rt = ResponseType.objects.get(type="Audit")
        except ResponseType.DoesNotExist:
            self.stderr.write(f"No such ResponseType {stage}")

        try:
            ms = MarkingSession.objects.get(label=session)
        except MarkingSession.DoesNotExist:
            self.stderr.write(f"No such Marking Session {session}")

        points = self.get_points(file)
        answer_map = self.get_option_map(option_map)

        for _, point in points.iterrows():
            if point["section"] == "Practice":
                continue

            if pd.isna(point["question number"]):
                self.stderr.write(
                    f"Bad value for question number {point['question number']} in row {_}"
                )
                continue

            responses_added = 0
            responses_overidden = 0
            existing_responses = 0

            if point["section"] == "":
                continue

            c_args = {}
            if (
                point.get("council type") is not None
                and pd.isna(point["council type"]) is False
            ):
                types = point["council type"].strip()
                if types != "":
                    types = self.scrub_council_type(types.split(","))
                    c_args["type__in"] = types

            if (
                point.get("council country", None) is not None
                and pd.isna(point["council country"]) is False
            ):
                countries = point["council country"].strip()
                if countries != "":
                    countries = countries.split(",")
                    c_args["country__in"] = [c.lower() for c in countries]

            if (
                point.get("council list") is not None
                and pd.isna(point["council list"]) is False
            ):
                councils = point["council list"].strip()
                if councils != "" and "Single-Tier" not in councils.split(","):
                    councils = [c.strip() for c in councils.split(",")]
                    c_args = {"name__in": councils}

            councils = PublicAuthority.objects.filter(marking_session=ms, **c_args)

            q_args = {"number": point["question number"]}
            if (
                not pd.isna(point["question part"])
                and point.get("question part", None) is not None
            ):
                q_args["number_part"] = point["question part"].strip()

            try:
                question = Question.objects.get(
                    section__marking_session=ms,
                    section__title=point["section"],
                    **q_args,
                )
            except Question.DoesNotExist:
                self.print_info(
                    f"no matching question for {point['section']}, {q_args}"
                ), 1
                continue

            copy_last_year = False
            if not pd.isna(point["copy last year answer"]):
                if point["copy last year answer"] == "Y":
                    copy_last_year = True
                    previous_question = question.previous_question

            if copy_last_year is False:
                answer = point["answer in GRACE"].strip()
                try:
                    option = Option.objects.get(question=question, description=answer)
                except Option.DoesNotExist:
                    self.print_info(
                        f"no matching option for {question.number_and_part}, {point['section']} - '{answer}'",
                        1,
                    )
                    continue

            for council in councils:
                add_response = False
                override_response = False

                options = None
                if copy_last_year:
                    try:
                        prev_response = Response.objects.get(
                            question=previous_question,
                            authority=council,
                            response_type=prev_rt,
                        )
                    except Response.DoesNotExist:
                        self.print_info(
                            f"no previous response exists for {council.name} for {question.number_and_part}, {question.section.title}"
                        )
                        continue
                    except Response.MultipleObjectsReturned:
                        self.print_info(
                            f"multiple previous responses exist for {council.name} for {question.number_and_part}, {question.section.title}"
                        )
                        continue

                    try:
                        if question.question_type == "multiple_choice":
                            options = []
                            for opt in prev_response.multi_option.all():
                                answer = self.get_mapped_answer(
                                    opt.description, question, answer_map
                                )
                                print(f"checking for {answer} in multi choice")
                                new_opt = Option.objects.get(
                                    question=question, description=answer
                                )
                                print("found answer")
                                options.append(new_opt)
                        else:
                            answer = self.get_mapped_answer(
                                prev_response.option.description, question, answer_map
                            )
                            option = Option.objects.get(
                                question=question, description=answer
                            )
                    except Option.DoesNotExist:
                        self.print_info(
                            f"no matching option for {question.number_and_part}, {point['section']} - '{prev_response.option.description}'",
                            1,
                        )
                        continue

                try:
                    response = Response.objects.get(
                        question=question, authority=council, response_type=rt
                    )
                    if question.question_type == "multiple_choice":
                        if response.multi_option is not None:
                            options = [x.id for x in response.multi_option.all()]
                            if option.id not in options:
                                self.print_info(
                                    f"{YELLOW}existing response does not contain expected response for {question.number_and_part}, {point['section']}, {council.name}{NOBOLD}",
                                    1,
                                )
                    else:
                        if response.option != option:
                            self.print_info(
                                f"{YELLOW}different existing response for {question.number_and_part}, {point['section']}, {council.name}{NOBOLD}",
                                1,
                            )
                        if point.get("override_response", None) is not None:
                            override_response = True
                    self.print_info(
                        f"response exists for {council.name} for {question.number_and_part}, {question.section.title}"
                    )
                    existing_responses += 1
                except Response.DoesNotExist:
                    add_response = True

                response_opts = {
                    "user": u,
                    "question": question,
                    "authority": council,
                    "response_type": rt,
                    "private_notes": "Automatically assigned mark",
                }
                if copy_last_year:
                    response_opts["public_notes"] = prev_response.public_notes
                    response_opts["page_number"] = prev_response.page_number
                    response_opts["evidence"] = prev_response.evidence
                    response_opts["private_notes"] = (
                        prev_response.private_notes + "\nAutomatically assigned mark"
                    )

                    if pd.isna(point["evidence notes"]) is False:
                        response_opts["evidence"] = point["evidence notes"]
                    if pd.isna(point["evidence link"]) is False:
                        response_opts["public_notes"] = point["evidence link"]
                else:
                    if pd.isna(point["page no"]) is False:
                        response_opts["page_number"] = point["page no"]
                    if pd.isna(point["evidence link"]) is False:
                        response_opts["public_notes"] = point["evidence link"]
                    if pd.isna(point["evidence notes"]) is False:
                        response_opts["evidence"] = point["evidence notes"]
                    if (
                        pd.isna(point["private notes"]) is False
                        and point["private notes"] != "n/a"
                    ):
                        response_opts["private_notes"] = (
                            str(point["private notes"])
                            + "\nAutomatically assigned mark"
                        )

                if add_response:
                    responses_added += 1
                    self.print_info(
                        f"creating response for {council.name} for {question.number_and_part}, {question.section.title}"
                    )

                    if commit:
                        if question.question_type == "multiple_choice":
                            r = Response.objects.create(**response_opts)
                            if options is not None:
                                for o in options:
                                    r.multi_option.add(o)
                            else:
                                r.multi_option.add(option.id)
                        else:
                            response_opts["option"] = option
                            r = Response.objects.create(**response_opts)

                elif override_response or update_existing_responses:
                    responses_overidden += 1
                    self.print_info(
                        f"overriding response for {council.name} for {question.number_and_part}, {question.section.title}",
                        1,
                    )

                    if question.question_type != "multiple_choice":
                        response.option = option

                    response.private_notes = (
                        response_opts["private_notes"]
                        + "\n"
                        + "Overridden by automatic assignment"
                    )

                    response.public_notes = response_opts["public_notes"]
                    response.evidence = response_opts["evidence"]
                    response.page_number = response_opts["page_number"]

                    if commit:
                        response.save()
                        if question.question_type == "multiple_choice":
                            response.multi_option.clear()
                            if options is not None:
                                for o in options:
                                    response.multi_option.add(o)
                            else:
                                response.multi_option.add(option.id)

            self.print_info(
                f"{GREEN}Added {responses_added} responses for {question.section.title} {question.number_and_part}, {existing_responses} existing responses, {responses_overidden} responses overridden{NOBOLD}",
                1,
            )
        if not commit:
            self.print_info(
                f"{YELLOW}call with --commit to commit changed to database{NOBOLD}",
                1,
            )
