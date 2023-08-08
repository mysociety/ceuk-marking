from django.core.management.base import BaseCommand

from crowdsourcer.models import Response, ResponseType
from crowdsourcer.scoring import get_duplicate_responses

YELLOW = "\033[33m"
NOBOLD = "\033[0m"


class Command(BaseCommand):
    help = "Remove exact duplicate responses"

    quiet = False

    def add_arguments(self, parser):
        parser.add_argument("--commit", action="store_true", help="commits DB change")
        parser.add_argument(
            "--quiet", action="store_true", help="do not print out debug"
        )

    def msg_out(self, message, always=False):
        if not always and self.quiet:
            return

        self.stdout.write(message)

    def handle(self, *args, **kwargs):
        if kwargs["quiet"]:
            self.quiet = True

        if not kwargs["commit"]:
            self.msg_out(
                f"{YELLOW}Not commiting changes. Call with --commit to update database{NOBOLD}",
                True,
            )

        duplicates = get_duplicate_responses()

        self.msg_out(
            f"Potential responses with exact duplicates count is {duplicates.count()}"
        )

        rt = ResponseType.objects.get(type="Audit")

        potentials = {}
        for d in duplicates:
            rs = Response.objects.filter(
                question_id=d["question_id"],
                authority_id=d["authority_id"],
                response_type=rt,
            ).select_related("question", "authority")

            for r in rs:
                if potentials.get(r.authority.name, None) is None:
                    potentials[r.authority.name] = {}

                if (
                    potentials[r.authority.name].get(r.question.number_and_part, None)
                    is None
                ):
                    potentials[r.authority.name][r.question.number_and_part] = []

                potentials[r.authority.name][r.question.number_and_part].append(r)

        dupes = []
        for authority, questions in potentials.items():
            for question, responses in questions.items():
                diff = False
                first = responses[0]
                first_multi = sorted([o.pk for o in first.multi_option.all()])
                for response in responses:
                    for prop in [
                        "evidence",
                        "public_notes",
                        "page_number",
                        "private_notes",
                        "agree_with_response",
                        "foi_answer_in_ror",
                    ]:
                        if getattr(response, prop) != getattr(first, prop):
                            diff = True

                    if response.option is None and first.option is not None:
                        diff = True
                    elif response.option is not None and first.option is None:
                        diff = True
                    elif (
                        response.option is not None
                        and first.option is not None
                        and response.option.id != first.option.id
                    ):
                        diff = True

                    multi = sorted([o.pk for o in response.multi_option.all()])
                    if multi != first_multi:
                        diff = True

                if not diff:
                    dupes.append(responses[1:])

        self.msg_out(f"Actual responses with exact duplicates count is {len(dupes)}")

        response_count = 0
        for dupe in dupes:
            for r in dupe:
                response_count += 1
                if kwargs["commit"]:
                    r.delete()

        if kwargs["commit"]:
            self.msg_out(f"Deleted {response_count} responses as duplicates", True)
        else:
            self.msg_out(
                f"{YELLOW}Would have deleted {response_count} responses as duplicates{NOBOLD}",
                True,
            )

        return "done"
