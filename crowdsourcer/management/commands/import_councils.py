from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

import pandas as pd

from crowdsourcer.models import Marker, PublicAuthority, ResponseType

YELLOW = "\033[33m"
RED = "\033[31m"
GREEN = "\033[32m"
NOBOLD = "\033[0m"


class Command(BaseCommand):
    help = "import councils"

    council_file = settings.BASE_DIR / "data" / "council_emails.csv"

    def add_arguments(self, parser):
        parser.add_argument(
            "-q", "--quiet", action="store_true", help="Silence progress bars."
        )

        parser.add_argument(
            "--add_users", action="store_true", help="add users to database"
        )

    def handle(self, quiet: bool = False, *args, **options):
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
                print(
                    f"No council with GSS of {row['gssNumber']}, {row['council']} found"
                )
                continue

            if Marker.objects.filter(authority=council).exists():
                print(f"user already exists for council: {row['council']}")

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
