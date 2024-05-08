from django.core.management.base import BaseCommand

from crowdsourcer.models import MarkingSession
from crowdsourcer.scoring import get_duplicate_responses, get_exact_duplicates

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

        parser.add_argument(
            "--session",
            action="store",
            help="Marking session to use remove duplicates from",
        )

    def msg_out(self, message, always=False):
        if not always and self.quiet:
            return

        self.stdout.write(message)

    def handle(self, *args, **kwargs):
        if kwargs["quiet"]:
            self.quiet = True

        session_label = kwargs.get("session", None)
        try:
            session = MarkingSession.objects.get(label=session_label)
        except MarkingSession.DoesNotExist:
            self.stderr.write(f"No session with that name: {session_label}")
            return

        if not kwargs["commit"]:
            self.msg_out(
                f"{YELLOW}Not commiting changes. Call with --commit to update database{NOBOLD}",
                True,
            )

        duplicates = get_duplicate_responses(session)

        self.msg_out(
            f"Potential responses with exact duplicates count is {duplicates.count()}"
        )

        dupes = get_exact_duplicates(duplicates, session)

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
