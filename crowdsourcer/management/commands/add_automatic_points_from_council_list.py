from collections import defaultdict

from django.contrib.auth.models import User

import pandas as pd

from crowdsourcer.import_utils import BaseImporter
from crowdsourcer.models import Option, Question, Response


class Command(BaseImporter):
    help = "Apply a list of responses to councils"

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
            "--response_list",
            action="store",
            required=True,
            help="CSV file containing the councils and responses",
        )

        parser.add_argument(
            "--question_list",
            action="store",
            required=True,
            help="CSV file containing the questions",
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
            "--authority_map",
            action="store",
            help="CSV file containing bad_name, good_name columns to map from bad councils names",
        )

        parser.add_argument(
            "--update_existing_responses",
            action="store_true",
            help="Always update existings responses",
        )

        parser.add_argument(
            "--commit", action="store_true", help="Commits changes to DB"
        )

    def get_df(self, file):
        df = pd.read_csv(file)

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
        response_list: str = "",
        question_list: str = "",
        stage: str = "",
        session: str = "",
        option_map: str = "",
        authority_map: str = "",
        update_existing_responses: bool = False,
        *args,
        **kwargs,
    ):
        self.quiet = quiet

        u, _ = User.objects.get_or_create(
            username="Auto_point_script",
        )

        rt, ms = self.get_stage_and_session(stage, session)

        responses = self.get_df(response_list)
        questions = self.get_df(question_list)
        answer_map = self.get_option_map(option_map)
        self.council_lookup = self.get_council_lookup()
        self.set_authority_map(authority_map)

        page_number = 0
        evidence = "Council owns less than 100 homes or no homes at all"

        responses_added = 0
        responses_overidden = 0
        existing_responses = 0
        with self.get_atomic_context(commit):
            for _, q in questions.iterrows():
                q_args = {"number": q["question_number"]}
                if (
                    not pd.isna(q["question_part"])
                    and q.get("question_part", None) is not None
                ):
                    q_args["number_part"] = q["question_part"].strip()

                try:
                    question = Question.objects.get(
                        section__marking_session=ms,
                        section__title=q["section"],
                        **q_args,
                    )
                except Question.DoesNotExist:
                    self.print_error(
                        f"no matching question for {q['section']}, {q_args}"
                    )
                    continue

                for _, r in responses.iterrows():

                    council_name = r["public_body"]
                    council = self.get_authority(council_name, ms)
                    if council is None:
                        self.print_error(f"{council_name} not found")
                        continue

                    answer = self.get_mapped_answer(
                        r["Staff Review"].strip(), question, answer_map
                    )
                    try:
                        option = Option.objects.get(
                            question=question, description=answer
                        )
                    except Option.DoesNotExist:
                        self.print_error(
                            f"no matching option for {question.number_and_part}, {q['section']} - '{answer}'"
                        )
                        continue

                    add_response = False

                    options = None
                    try:
                        response = Response.objects.get(
                            question=question, authority=council, response_type=rt
                        )
                        if question.question_type == "multiple_choice":
                            if response.multi_option is not None:
                                options = [x.id for x in response.multi_option.all()]
                                if option.id not in options:
                                    self.print_info(
                                        f"existing response does not contain expected response for {question.number_and_part}, {q['section']}, {council.name}"
                                    )
                        else:
                            if response.option != option:
                                self.print_info(
                                    f"different existing response for {question.number_and_part}, {q['section']}, {council.name}"
                                )
                        self.print_debug(
                            f"response exists for {council.name} for {question.number_and_part}, {q['section']}"
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
                        "page_number": page_number,
                        "evidence": evidence,
                        "public_notes": r["request_url"],
                    }

                    if add_response:
                        responses_added += 1
                        self.print_debug(
                            f"creating response for {council.name} for {question.number_and_part}, {q['section']}"
                        )

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

                    elif update_existing_responses:
                        responses_overidden += 1
                        self.print_info(
                            f"overriding response for {council.name} for {question.number_and_part}, {q['section']}"
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

                        response.save()
                        if question.question_type == "multiple_choice":
                            response.multi_option.clear()
                            if options is not None:
                                for o in options:
                                    response.multi_option.add(o)
                            else:
                                response.multi_option.add(option.id)

                self.print_success(
                    f"Added {responses_added} responses for {q['section']} {question.number_and_part}, {existing_responses} existing responses, {responses_overidden} responses overridden"
                )
        if not commit:
            self.print_info(
                "call with --commit to commit changed to database",
            )
