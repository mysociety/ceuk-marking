from django.conf import settings
from django.contrib.auth.models import User

import pandas as pd

from crowdsourcer.import_utils import BaseImporter
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


class Command(BaseImporter):
    help = "import councils"

    council_file = (
        settings.BASE_DIR / "data" / "scorecards-2025" / "council_contacts.csv"
    )

    council_map = {
        "Cheshire West & Chester Council": "Cheshire West and Chester Council",
        "Cumbria Council": "Cumbria County Council",
        "East Sussex Council": "East Sussex County Council",
        "York and North Yorkshire Combined Authority": "York and North Yorkshire Mayoral Combined Authority",
        "East Midlands Combined Authority": "East Midlands Combined County Authority",
    }

    council_column = "councilInternalName"
    commit = False
    quiet = False

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
        if row.get("gssNumber") and not pd.isna(row["gssNumber"]):
            try:
                council = PublicAuthority.objects.get(unique_id=row["gssNumber"])
                return council
            except PublicAuthority.DoesNotExist:
                print(f"no gss found {row['gssNumber']}")

        if row.get("councilInternalName"):
            try:
                council = PublicAuthority.objects.get(
                    name=self.council_map.get(
                        row[self.council_column], row[self.council_column]
                    )
                )
                return council
            except PublicAuthority.DoesNotExist:
                self.print_error(f"no name found: {row[self.council_column]}")
                return None
            except PublicAuthority.MultipleObjectsReturned:
                self.print_error(f"multiple results for: {row[self.council_column]}")
                return None

        return None

    def handle(self, quiet: bool = False, session: str = None, *args, **options):
        if options.get("council_list") is not None:
            self.council_file = options["council_list"]

        if quiet:
            self.quiet = True

        df = pd.read_csv(
            self.council_file,
            usecols=["firstName", "surname", self.council_column, "email", "gssNumber"],
        )

        add_users = options["add_users"]
        if add_users:
            self.commit = True

        session = MarkingSession.objects.get(label=session)
        rt = ResponseType.objects.get(type="Right of Reply")
        count = 0

        if not add_users:
            self.print_info("Run with add_users to add users")
        with self.get_atomic_context(self.commit):
            for index, row in df.iterrows():
                if pd.isna(row["email"]):
                    continue

                council = self.get_council(row)

                if not council:
                    self.print_error(f"No council {row[self.council_column]} found")
                    continue

                if council.do_not_mark:
                    self.print_info(
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
                        self.print_info(
                            f"user already exists for council: {row[self.council_column]}"
                        )
                        if not m.send_welcome_email:
                            m.send_welcome_email = True
                            m.save()
                        if not m.user.is_active:
                            m.user.is_active = True
                            m.user.save()
                        continue

                if User.objects.filter(username=row["email"]).exists():
                    u = User.objects.get(username=row["email"])
                    if not u.is_active:
                        u.is_active = True
                        u.save()

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
                        self.print_info(
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
                        self.print_info(
                            f"updating marker to council: {row['email']} ({council}, {u.marker.authority}"
                        )
                        u.marker.authority = council
                        u.marker.send_welcome_email = True
                        u.marker.save()
                        u.marker.marking_session.set([session])
                    elif (
                        u.marker.authority is not None and u.marker.authority != council
                    ):
                        self.print_info(
                            f"dual email for councils: {row['email']} ({council}, {u.marker.authority}"
                        )
                        for c in [council, u.marker.authority]:
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
                    self.print_info(f"user already exists for email: {row['email']}")
                    continue

                count += 1
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
                    defaults={
                        "send_welcome_email": True,
                    },
                )
                self.print_debug(f"adding {row['email']} for {council}")
                m.marking_session.set([session])

            self.print_success(f"Added {count} users")
