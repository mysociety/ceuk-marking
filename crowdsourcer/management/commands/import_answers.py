import re

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
            "--file",
            action="store",
            required=True,
            help="CSV file containing the answers",
        )

        parser.add_argument(
            "--update_existing_responses",
            action="store_true",
            help="Update existings responses as well",
        )

        parser.add_argument(
            "--commit", action="store_true", help="Commits changes to DB"
        )

    def print_info(self, message, level=2, colour=None):
        if self.quiet and level > 1:
            return

        if colour is not None:
            message = f"{colour}{message}{NOBOLD}"

        self.stdout.write(message)

    def get_answers(self, file):
        df = pd.read_csv(file)

        return df

    def handle(
        self,
        quiet: bool = False,
        commit: bool = False,
        file: str = "",
        session: str = "",
        update_existing_responses: bool = False,
        *args,
        **kwargs,
    ):
        self.quiet = quiet

        self.print_info("Please do not use this for a live server", 1, colour=RED)

        u, _ = User.objects.get_or_create(
            username="Auto_answer_script",
        )

        try:
            rt = ResponseType.objects.get(type="Audit")
        except ResponseType.DoesNotExist:
            self.print_info("No such ResponseType Audit", 1, colour=RED)

        try:
            ms = MarkingSession.objects.get(label=session)
        except MarkingSession.DoesNotExist:
            self.stderr.write(f"No such Marking Session {session}", 1, colour=RED)

        answers = self.get_answers(file)

        responses_added = 0
        responses_skipped = 0
        existing_responses = 0

        for _, answer in answers.iterrows():
            if pd.isna(answer["question-number"]):
                self.print_info(
                    f"Bad value for question number {answer['question-number']} in row {_}",
                    colour=YELLOW,
                )
                responses_skipped += 1
                continue

            add_response = False
            existing_response = False

            if answer["section"] == "":
                self.print_info(
                    f"Bad section ({answer['section']}) for question number {answer['question-number']} in row {_}",
                    colour=YELLOW,
                )
                responses_skipped += 1
                continue

            council_name = answer["council name"]
            council = PublicAuthority.objects.get(marking_session=ms, name=council_name)

            q_parts = re.match(r"(\d+)([a-z]?)", answer["question-number"])
            q_args = {"number": q_parts.groups()[0]}
            if len(q_parts.groups()) == 2 and q_parts.groups()[1] != "":
                q_args["number_part"] = q_parts.groups()[1]

            try:
                question = Question.objects.get(
                    section__marking_session=ms,
                    section__title=answer["section"],
                    **q_args,
                )
            except Question.DoesNotExist:
                self.print_info(
                    f"no matching question for {answer['section']}, {q_args}",
                    1,
                    colour=YELLOW,
                )
                responses_skipped += 1
                continue

            desc = answer["answer"].strip()
            try:
                if question.question_type == "multiple_choice":
                    opts = desc.split(",")
                    options = []
                    for o in opts:
                        new_opt = Option.objects.get(question=question, description=o)
                        options.append(new_opt)
                else:
                    option = Option.objects.get(question=question, description=desc)
            except Option.DoesNotExist:
                self.print_info(
                    f"no matching option for {question.number_and_part}, {answer['section']} - '{desc}'",
                    colour=YELLOW,
                )
                responses_skipped += 1
                continue
            except Option.MultipleObjectsReturned:
                self.print_info(
                    f"multiple matching option for {question.number_and_part}, {answer['section']} - '{desc}'",
                    colour=YELLOW,
                )
                responses_skipped += 1
                continue

            try:
                response = Response.objects.get(
                    question=question, authority=council, response_type=rt
                )
                if question.question_type == "multiple_choice":
                    if response.multi_option is not None:
                        if option.id not in options:
                            self.print_info(
                                f"existing response does not contain expected response for {question.number_and_part}, {answer['section']}, {council.name}",
                                colour=YELLOW,
                            )
                else:
                    if response.option != option:
                        self.print_info(
                            f"different existing response for {question.number_and_part}, {answer['section']}, {council.name}",
                            1,
                            colour=YELLOW,
                        )
                self.print_info(
                    f"response exists for {council.name} for {question.number_and_part}, {question.section.title}",
                    colour=YELLOW,
                )
                existing_response = True
                existing_responses += 1
            except Response.DoesNotExist:
                add_response = True
            except Response.MultipleObjectsReturned:
                self.print_info(
                    f"multiple responses for {council.name} for {question.number_and_part}, {question.section.title}",
                    colour=YELLOW,
                )
                responses_skipped += 1
            except ValueError:
                self.print_info(
                    f"problem with response for {council.name} for {question.number_and_part}, {question.section.title}",
                    colour=YELLOW,
                )
                responses_skipped += 1

            if add_response:
                responses_added += 1
                self.print_info(
                    f"creating response for {council.name} for {question.number_and_part}, {question.section.title}",
                    colour=GREEN,
                )
                if commit:
                    if question.question_type == "multiple_choice":
                        r = Response.objects.create(
                            user=u,
                            question=question,
                            authority=council,
                            response_type=rt,
                            private_notes="Automatically assigned mark",
                        )
                        for o in options:
                            r.multi_option.add(o.id)
                    else:
                        response_opts = {
                            "user": u,
                            "question": question,
                            "authority": council,
                            "response_type": rt,
                            "option": option,
                            "private_notes": "Automatically imported mark",
                        }
                        if pd.isna(answer["page_number"]) is False:
                            response_opts["page_number"] = answer["page_number"]
                        if pd.isna(answer["evidence"]) is False:
                            response_opts["public_notes"] = answer["evidence"]
                        if pd.isna(answer["public_notes"]) is False:
                            response_opts["evidence"] = answer["public_notes"]

                        r = Response.objects.create(**response_opts)

            if existing_response and update_existing_responses:
                defaults = {
                    "private_notes": "Automatically imported mark",
                }
                if pd.isna(answer["page_number"]) is False:
                    defaults["page_number"] = answer["page_number"]
                if pd.isna(answer["evidence"]) is False:
                    defaults["public_notes"] = answer["evidence"]
                if pd.isna(answer["public_notes"]) is False:
                    defaults["evidence"] = answer["public_notes"]

                if question.question_type != "multiple_choice":
                    defaults["option"] = option

                r, _ = Response.objects.update_or_create(
                    user=u,
                    question=question,
                    authority=council,
                    response_type=rt,
                    defaults=defaults,
                )

                if question.question_type == "multiple_choice":
                    r.multi_option.clear()
                    for o in options:
                        r.multi_option.add(o.id)

        if not commit:
            self.print_info(
                "call with --commit to commit changed to database", 1, colour=YELLOW
            )

        if responses_skipped:
            colour = YELLOW
        else:
            colour = GREEN
        self.print_info(
            f"{responses_added} reponses added, {existing_responses} existing responses, {responses_skipped} responses with error",
            1,
            colour=colour,
        )
