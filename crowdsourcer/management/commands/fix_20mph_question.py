from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

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

    sheets = [
        {
            "sheet": "Transport Q4 - 20mph",
            "section": "Transport",
            "number": 4,
            "council_col": "Council name",
            "score_col": "Award point - only 1 tier",
            "evidence": "Evidence link",
            "default_if_missing": 0,
            "missing_filter": {
                "type__in": ["CTY", "UTA", "LBO", "MTD"],
                "country": "england",
            },
            "type": "yes_no",
        },
    ]

    def add_arguments(self, parser):
        parser.add_argument(
            "-q", "--quiet", action="store_true", help="Silence debug data."
        )

        parser.add_argument("--commit", action="store_true", help="Save the options")

    def get_question(self, details):
        ms = MarkingSession.objects.get(label="Scorecards 2023")
        q = None
        try:
            args = {
                "section__marking_session": ms,
                "section__title": details["section"],
                "number": details["number"],
            }
            if details.get("number_part", None) is not None:
                args["number_part"] = details["number_part"]

            q = Question.objects.get(**args)
        except Question.DoesNotExist:
            self.print_info("did not find question", 1)

        return q

    def import_answers(self, user, rt, q, details):
        count = 0
        auto_zero = 0
        bad_authority_count = 0
        if details.get("gss_col", details.get("council_col", None)) is not None:
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
                    self.print_info(f"Adding response for {council.name}")
                    if self.commit:
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
        q = self.get_question(details)
        if q is None:
            self.print_info(
                f"{RED}Could not find questions {details['section']}, {details['number']}, {details.get('number_part', '')}{NOBOLD}",
                1,
            )
            return

        self.import_answers(user, self.rt, q, details)

    def print_info(self, message, level=2):
        if self.quiet and level > 1:
            return

        print(message)

    def handle(
        self,
        quiet: bool = False,
        commit: bool = False,
        *args,
        **kwargs,
    ):
        self.quiet = quiet
        self.commit = commit

        if commit is False:
            self.print_info(
                f"{RED}Not creating responses, call with --commit to do so{NOBOLD}", 1
            )

        user, _ = User.objects.get_or_create(username="National_Importer")
        self.rt = ResponseType.objects.get(type="Audit")
        for details in self.sheets:
            sheet = details["sheet"]
            self.handle_sheet(sheet, details, user)
