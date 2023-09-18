from collections import defaultdict

from django.core.management.base import BaseCommand

from crowdsourcer.models import Question, Response, ResponseType

YELLOW = "\033[33m"
RED = "\033[31m"
GREEN = "\033[32m"
NOBOLD = "\033[0m"


class Command(BaseCommand):
    help = "convert former multi_option questions to single option"

    def add_arguments(self, parser):
        parser.add_argument("-q", "--quiet", action="store_true", help="Silence debug.")

        parser.add_argument(
            "--commit", action="store_true", help="commit changes to database"
        )

    def convert_to_single_response(self):
        rt = ResponseType.objects.get(type="Audit")
        valid_questions = Question.objects.exclude(question_type="multiple_choice")
        responses = (
            Response.objects.filter(question__in=valid_questions, response_type=rt)
            .exclude(multi_option__isnull=True)
            .select_related("question", "question__section", "authority")
            .order_by("question_id", "id")
        )

        self.print_msg(f"examining {responses.count()} responses")

        counts = defaultdict(int)
        for response in responses:
            q = response.question
            a = response.authority.name
            if response.multi_option.count() > 1:
                self.print_msg(
                    f"{YELLOW}multiple response {response.id}, {a} {q.section.title} {q.number_and_part}{NOBOLD}",
                    True,
                )
            elif response.option is not None:
                self.print_msg(
                    f"{YELLOW}existing response {response.id}, {a} {q.section.title} {q.number_and_part}{NOBOLD}",
                    True,
                )
            else:
                counts[q.section.title + ": " + q.number_and_part] += 1
                if self.commit:
                    response.option = response.multi_option.all()[0]
                    response.multi_option.set([])
                    response.save()

        for q, count in counts.items():
            self.print_msg(f"updated {count} items for {q}")

    def print_msg(self, msg, always=False):
        should_print = not self.quiet
        if always:
            should_print = True

        if should_print:
            self.stdout.write(msg)

    def handle(self, quiet: bool = False, commit: bool = False, *args, **kwargs):
        self.quiet = quiet
        self.commit = commit

        if not self.commit:
            self.print_msg(
                f"{YELLOW}Not updating database, call with --commit to do so{NOBOLD}",
                True,
            )
        self.convert_to_single_response()

        self.print_msg(f"{GREEN}done{NOBOLD}")
