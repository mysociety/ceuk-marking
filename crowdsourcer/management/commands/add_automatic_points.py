from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

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
    help = "Add automatic points"

    points = [
        {
            "section": "",
            "question_number": "",
            "question_part": "",
            "council_type": "",
            "council_country": "",
            "option_value": "",
        },
        {
            "section": "Waste Reduction & Food",
            "question_number": "1",
            "question_part": "a",
            "council_type": None,
            "council_country": ["scotland"],
            "option_value": "Yes",
        },
        {
            "section": "Waste Reduction & Food",
            "question_number": "1",
            "question_part": "b",
            "council_type": None,
            "council_country": ["scotland"],
            "min_score": 1,
            "option_value": "The council requires event organisers to provide additional information about their environmental commitments",
        },
        {
            "section": "Waste Reduction & Food",
            "question_number": "7",
            "question_part": None,
            "council_type": None,
            "council_country": ["scotland", "wales"],
            "option_value": "Yes",
        },
        {
            "section": "Buildings & Heating",
            "question_number": "4",
            "question_part": None,
            "council_type": None,
            "council_country": ["scotland"],
            # XXX check answer
            "min_score": 1,
            "option_value": "Yes, and there is a target date of 2050",
        },
        {
            "section": "Buildings & Heating",
            "question_number": "5",
            "question_part": None,
            # XXX check if also GLA?
            "council_type": ["LBO"],
            "council_country": ["england"],
            "option_value": "The council convenes or is a member of a local retrofit partnership AND convenes or supports a programme for retro-fitting locally",
            "evidence": "https://londoncouncils.gov.uk/our-key-themes/climate-change/retrofit-london-programme",
        },
        {
            "section": "Governance & Finance",
            "question_number": "6",
            "question_part": None,
            "council_type": None,
            "council_country": ["scotland"],
            "min_score": 1,
            "option_value": "Yes, two or more options of criteria A is met",
            "evidence": "https://www.gov.scot/publications/procurement-reform-scotland-act-2014-statutory-guidance/pages/3/",
            "override_response": True,
        },
        {
            "section": "Collaboration & Engagement",
            "question_number": "2",
            "question_part": "b",
            "council_type": None,
            "council_country": ["scotland"],
            "min_score": 1,
            "option_value": "The council has published an annual report",
        },
        {
            "section": "Collaboration & Engagement",
            "question_number": "4",
            "question_part": None,
            "council_type": None,
            "council_country": ["scotland"],
            "min_score": 1,
            "option_value": "1 or 2 memberships or case studies",
        },
    ]

    def add_arguments(self, parser):
        parser.add_argument(
            "-q", "--quiet", action="store_true", help="Silence debug text."
        )

        parser.add_argument(
            "--commit", action="store_true", help="Commits changes to DB"
        )

    def print_info(self, message, level=2):
        if self.quiet and level > 1:
            return

        print(message)

    def handle(self, quiet: bool = False, commit: bool = False, *args, **kwargs):
        self.quiet = quiet

        u, _ = User.objects.get_or_create(
            username="Auto_point_script",
        )
        rt = ResponseType.objects.get(type="Audit")

        for point in self.points:
            responses_added = 0
            responses_overidden = 0
            existing_responses = 0

            if point["section"] == "":
                continue

            c_args = {}
            if point.get("council_type", None) is not None:
                c_args["type__in"] = point["council_type"]

            if point.get("council_country", None) is not None:
                c_args["country__in"] = point["council_country"]

            councils = PublicAuthority.objects.filter(**c_args)

            q_args = {"number": point["question_number"]}
            if point.get("question_part", None) is not None:
                q_args["number_part"] = point["question_part"]

            try:
                question = Question.objects.get(
                    section__title=point["section"], **q_args
                )
            except Question.DoesNotExist:
                print(f"no matching question for {point['section']}, {q_args}")
                continue

            try:
                option = Option.objects.get(
                    question=question, description=point["option_value"]
                )
            except Option.DoesNotExist:
                print(
                    f"no matching option for {question.number_and_part}, {point['section']} - {point['option_value']}"
                )
                continue

            for council in councils:
                add_response = False
                override_response = False

                try:
                    response = Response.objects.get(
                        question=question, authority=council, response_type=rt
                    )
                    if point.get("min_score", None) is not None:
                        score = 0
                        score_too_small = False
                        if response.option is not None:
                            if point["min_score"] > response.option.score:
                                score = response.option.score
                                score_too_small = True
                        elif response.multi_option is not None:
                            options = response.multi_option.all()
                            for opt in options:
                                score += opt.score
                            if point["min_score"] > score:
                                score_too_small = True

                        if score_too_small:
                            self.print_info(
                                f"{question.number_and_part}, {question.section} for {council.name} has score less than {point['min_score']} - {score}",
                                1,
                            )
                            if point.get("override_response", None) is not None:
                                override_response = True
                    else:
                        if question.question_type == "multiple_select":
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

                if add_response:
                    responses_added += 1
                    self.print_info(
                        f"creating response for {council.name} for {question.number_and_part}, {question.section.title}"
                    )
                    if commit:
                        if question.question_type == "multiple_select":
                            r = Response.objects.create(
                                user=u,
                                question=question,
                                authority=council,
                                response_type=rt,
                                private_notes="Automatically assigned mark",
                            )
                            r.multi_option.add(option.id)
                        else:
                            r = Response.objects.create(
                                user=u,
                                question=question,
                                authority=council,
                                response_type=rt,
                                option=option,
                                private_notes="Automatically assigned mark",
                            )

                        if point.get("evidence", None) is not None:
                            r.public_notes = point["evidence"]
                            r.save()
                elif override_response:
                    responses_overidden += 1
                    self.print_info(
                        f"overriding response for {council.name} for {question.number_and_part}, {question.section.title}",
                        1,
                    )
                    response.option = option
                    response.private_notes = (
                        "Overridden by automatic assignment"
                        + "\n"
                        + response.private_notes
                    )
                    if point.get("evidence", None) is not None:
                        response.public_notes = (
                            point["evidence"] + "\n" + response.public_notes
                        )
                    if commit:
                        response.save()

            self.print_info(
                f"{GREEN}Added {responses_added} responses for {question.section.title} {question.number_and_part}, {existing_responses} existing responses, {responses_overidden} responses overridden{NOBOLD}",
                1,
            )
        if not commit:
            self.print_info(
                f"{YELLOW}call with --commit to commit changed to database{NOBOLD}",
                1,
            )
