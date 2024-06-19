from django.conf import settings
from django.core.management.base import BaseCommand

import pandas as pd

from crowdsourcer.models import MarkingSession, PublicAuthority

YELLOW = "\033[33m"
RED = "\033[31m"
GREEN = "\033[32m"
NOBOLD = "\033[0m"


class Command(BaseCommand):
    help = "add authorities to marking session"

    def add_arguments(self, parser):
        parser.add_argument(
            "-q", "--quiet", action="store_true", help="Silence progress bars."
        )

        parser.add_argument(
            "--all", action="store_true", help="add all existing authorities to session"
        )

        parser.add_argument(
            "--session", required=True, help="marking session to add to"
        )

        parser.add_argument("--council_list", help="list of councils to add")

    def add_to_session(self, authority, session):
        authority.marking_session.add(session)

    def handle(self, quiet: bool = False, *args, **options):
        try:
            session = MarkingSession.objects.get(label=options["session"])
        except MarkingSession.DoesNotExist:
            self.stderr.write(f"No such session {options['session']}")
            return

        if options["all"]:
            for authority in PublicAuthority.objects.all():
                self.add_to_session(authority, session)

            self.stdout.write(
                f"added {PublicAuthority.objects.count()} authorities to {session}"
            )

        elif options["council_list"]:
            council_file = options["council_list"]

            council_file = settings.BASE_DIR / "data" / council_file

            df = pd.read_csv(
                council_file,
                usecols=[
                    "council",
                    "gssNumber",
                ],
            )
            count = 0
            for index, row in df.iterrows():
                try:
                    authority = PublicAuthority.options.get(id=row["gssNumber"])
                    count += 1
                except PublicAuthority.DoesNotExist:
                    self.stderr.write(f"No authority found for {row['gssNumber']}")
                    continue

                self.add_to_session(authority, session)

            self.stdout.write(f"added {count} authorities to {session}")
