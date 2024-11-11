from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

import pandas as pd

from crowdsourcer.models import (
    Assigned,
    Marker,
    MarkingSession,
    PublicAuthority,
    ResponseType,
)

YELLOW = "\033[33m"
RED = "\033[31m"
GREEN = "\033[32m"
NOBOLD = "\033[0m"


class Command(BaseCommand):
    help = "import councils"

    council_file = (
        settings.BASE_DIR / "data" / "scorecards-2025" / "council_contacts.csv"
    )

    council_map = {
        "Cheshire West & Chester Council": "Cheshire West and Chester Council",
        "Cumbria Council": "Cumbria County Council",
        "East Sussex Council": "East Sussex County Council",
    }

    def add_arguments(self, parser):
        parser.add_argument(
            "-q", "--quiet", action="store_true", help="Silence progress bars."
        )

        parser.add_argument(
            "--session",
            action="store",
            required=True,
            help="Marking session to use assignments with",
        )

        parser.add_argument("--update_users", action="store_true", help="update users")

    def get_council(self, row):
        if row.get("gssNumber"):
            try:
                council = PublicAuthority.objects.get(unique_id=row["gssNumber"])
                return council
            except PublicAuthority.DoesNotExist:
                print("no gss found")
                return None

        if row.get("council"):
            try:
                council = PublicAuthority.objects.get(
                    name=self.council_map.get(row["council"], row["council"])
                )
                return council
            except PublicAuthority.DoesNotExist:
                print(f"no name found: {row['council']}")
                return None

        return None

    def handle(self, quiet: bool = False, session: str = None, *args, **options):
        if options.get("council_list") is not None:
            self.council_file = options["council_list"]

        if not options["update_users"]:
            self.stdout.write(
                f"{YELLOW}Not updateding users. Call with --update_users to update{NOBOLD}"
            )

        df = pd.read_csv(
            self.council_file,
            usecols=[
                "name",
                "council",
                "email",
            ],
        )

        session = MarkingSession.objects.get(label=session)
        rt = ResponseType.objects.get(type="Right of Reply")
        count = 0
        for index, row in df.iterrows():
            if pd.isna(row["email"]):
                continue

            council = self.get_council(row)

            if not council:
                self.stdout.write(f"No council {row['council']} found")
                continue

            if council.do_not_mark:
                self.stdout.write(
                    f"Not creating account for do not mark councils: {council.name}"
                )
                continue

            if Marker.objects.filter(
                authority=council, marking_session=session
            ).exists():
                m = Marker.objects.get(authority=council, marking_session=session)
                if m.user.is_active == False:
                    print(f"fixing details for {m.user.email}")
                    count += 1
                    m.user.is_active = True
                    m.send_welcome_email = True
                    if options["update_users"]:
                        m.user.save()
                        m.save()

        prefix = ""
        if not options["update_users"]:
            prefix = "would have "
        print(f"{prefix}set {count} council users to active")
