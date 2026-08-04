from datetime import datetime, timedelta
from typing import Optional

from crowdsourcer.import_utils import BaseImporter
from crowdsourcer.models import Marker, MarkingSession, ResponseType


class Command(BaseImporter):

    def add_arguments(self, parser):
        parser.add_argument(
            "--session",
            required=True,
            action="store",
            help="Marking session for users to disable",
        )

        parser.add_argument(
            "--stage",
            required=True,
            action="store",
            help="Stage for users to disable",
        )

        parser.add_argument(
            "--weeks_ago",
            required=True,
            action="store",
            help="How many weeks since first login to disable",
        )

        parser.add_argument("--verbose", action="store_true", help="more output")
        parser.add_argument("--commit", action="store_true", help="commit things")

    def get_marking_session(self, session) -> Optional[MarkingSession]:
        try:
            ms = MarkingSession.objects.get(label=session)
        except MarkingSession.DoesNotExist:
            self.print_error(f"No such session: {session}")
            return None

        return ms

    def get_response_type(self, name) -> Optional[ResponseType]:
        try:
            rt = ResponseType.objects.get(type=name)
        except ResponseType.DoesNotExist:
            self.print_error(f"No such stage: {name}")
            return None

        return rt

    def get_first_login_cutoff(self, weeks: int):
        w = timedelta(weeks=weeks)
        cutoff = datetime.now().astimezone() - w

        return cutoff

    def handle(
        self,
        session: str,
        verbose: bool = False,
        commit: bool = False,
        *args,
        **options,
    ):
        self.commit = commit
        self.quiet = not verbose

        self.session = self.get_marking_session(session)
        stage = self.get_response_type(options["stage"])
        cutoff = self.get_first_login_cutoff(int(options["weeks_ago"]))

        if self.session is None or stage is None or cutoff is None:
            return

        if not commit:
            self.print_info("call with --commit to save updates")

        self.print_info(f"Disabling all accounts that logged in before {cutoff}")

        with self.get_atomic_context(commit):
            markers = Marker.objects.filter(
                response_type=stage,
                marking_session=self.session,
                first_login__isnull=False,
                first_login__lt=cutoff,
            )

            self.print_info(
                f"disabling {markers.count()} users with login before {cutoff.isoformat()}"
            )

            for m in markers:
                self.print_debug(f"disabling account for {m.user.username}")
                m.user.is_active = False
                m.user.save()

        self.print_info("done")
