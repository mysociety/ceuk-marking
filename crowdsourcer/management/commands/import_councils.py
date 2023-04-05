from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

import pandas as pd

from crowdsourcer.models import Assigned, Marker, PublicAuthority, ResponseType

YELLOW = "\033[33m"
RED = "\033[31m"
GREEN = "\033[32m"
NOBOLD = "\033[0m"


class Command(BaseCommand):
    help = "import councils"

    council_file = settings.BASE_DIR / "data" / "merged_contacts.csv"

    def add_arguments(self, parser):
        parser.add_argument(
            "-q", "--quiet", action="store_true", help="Silence progress bars."
        )

        parser.add_argument(
            "--add_users", action="store_true", help="add users to database"
        )

        parser.add_argument("--council_list", help="file to import data from")

    def handle(self, quiet: bool = False, *args, **options):
        if options.get("council_list") is not None:
            self.council_file = options["council_list"]

        df = pd.read_csv(
            self.council_file,
            usecols=[
                "firstName",
                "surname",
                "council",
                "gssNumber",
                "email",
            ],
        )

        rt = ResponseType.objects.get(type="Right of Reply")
        for index, row in df.iterrows():
            if pd.isna(row["email"]) or pd.isna(row["gssNumber"]):
                continue

            try:
                council = PublicAuthority.objects.get(unique_id=row["gssNumber"])
            except PublicAuthority.DoesNotExist:
                self.stdout.write(
                    f"No council with GSS of {row['gssNumber']}, {row['council']} found"
                )
                continue

            if council.do_not_mark:
                self.stdout.write(
                    f"Not creating account for do not mark councils: {council.name}"
                )
                continue

            if Marker.objects.filter(authority=council).exists():
                self.stdout.write(f"user already exists for council: {row['council']}")
                continue

            if User.objects.filter(username=row["email"]).exists():
                u = User.objects.get(username=row["email"])
                if u.marker.authority is not None and u.marker.authority != council:
                    self.stdout.write(
                        f"dual email for councils: {row['email']} ({council}, {u.marker.authority}"
                    )
                    if options["add_users"]:
                        for c in [council, u.marker.authority]:
                            if options["add_users"]:
                                a, _ = Assigned.objects.update_or_create(
                                    user=u, authority=c
                                )
                        u.marker.authority = None
                        u.marker.save()
                    continue
                self.stdout.write(f"user already exists for email: {row['email']}")
                continue

            if options["add_users"] is True:
                u, created = User.objects.update_or_create(
                    username=row["email"],
                    defaults={
                        "email": row["email"],
                        "first_name": row["firstName"],
                        "last_name": row["surname"],
                    },
                )
                u.save()
                m, _ = Marker.objects.update_or_create(
                    user=u,
                    authority=council,
                    response_type=rt,
                )
