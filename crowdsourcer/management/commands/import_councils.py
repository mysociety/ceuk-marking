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

        parser.add_argument(
            "--add_users", action="store_true", help="add users to database"
        )

        parser.add_argument("--council_list", help="file to import data from")

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

                if (
                    m.user.email == row["email"]
                    and m.marking_session.filter(pk=session.pk).exists()
                ):
                    self.stdout.write(
                        f"user already exists for council: {row['council']}"
                    )
                    if not m.send_welcome_email:
                        m.send_welcome_email = True
                        m.save()
                    continue

            if User.objects.filter(username=row["email"]).exists():
                u = User.objects.get(username=row["email"])
                if not hasattr(u, "marker"):
                    m = Marker.objects.create(
                        user=u, authority=council, response_type=rt
                    )
                    m.marking_session.set([session])
                elif (
                    u.marker.authority == council
                    and not u.marker.marking_session.filter(pk=session.pk).exists()
                ):
                    u.marker.marking_session.set([session])
                    self.stdout.write(
                        f"updating marker to current session: {row['email']} ({council}, {u.marker.authority}"
                    )
                    u.marker.send_welcome_email = True
                    u.marker.save()
                elif (
                    u.marker.authority is None
                    and not Assigned.objects.filter(
                        user=u, authority=council, marking_session=session
                    ).exists()
                ):
                    self.stdout.write(
                        f"updating marker to council: {row['email']} ({council}, {u.marker.authority}"
                    )
                    if options["add_users"]:
                        u.marker.authority = council
                        u.marker.send_welcome_email = True
                        u.marker.save()
                        u.marker.marking_session.set([session])
                elif u.marker.authority is not None and u.marker.authority != council:
                    self.stdout.write(
                        f"dual email for councils: {row['email']} ({council}, {u.marker.authority}"
                    )
                    if options["add_users"]:
                        for c in [council, u.marker.authority]:
                            if options["add_users"]:
                                a, _ = Assigned.objects.update_or_create(
                                    user=u,
                                    authority=c,
                                    response_type=rt,
                                    marking_session=session,
                                )
                        u.marker.authority = None
                        u.marker.send_welcome_email = True
                        u.marker.save()
                        u.marker.marking_session.set([session])
                    continue

                if hasattr(u, "marker") and not u.marker.send_welcome_email:
                    u.marker.send_welcome_email = True
                    u.marker.save()
                self.stdout.write(f"user already exists for email: {row['email']}")
                continue

            firstname, surname = row["name"].split(" ", maxsplit=1)
            if options["add_users"] is True:
                u, created = User.objects.update_or_create(
                    username=row["email"],
                    defaults={
                        "email": row["email"],
                        "first_name": firstname,
                        "last_name": surname,
                    },
                )
                u.save()
                m, _ = Marker.objects.update_or_create(
                    user=u,
                    authority=council,
                    response_type=rt,
                    defaults={
                        "send_welcome_email": True,
                    },
                )
                m.marking_session.set([session])
