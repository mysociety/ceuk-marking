import re
from copy import copy

from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q

import pandas as pd

from crowdsourcer.models import (
    Assigned,
    Marker,
    MarkingSession,
    PublicAuthority,
    ResponseType,
    Section,
)

YELLOW = "\033[33m"
RED = "\033[31m"
GREEN = "\033[32m"
NOBOLD = "\033[0m"

COLUMN_NAMES = (
    "first_name",
    "last_name",
    "email",
    "council_area",
    "type_of_volunteering",
    "assigned_section",
)

USECOLS = (
    "First name",
    "Last name",
    "Email",
    "Council Area",
    "Type of Volunteering",
    "Assigned Section",
)


class Command(BaseCommand):
    help = "import volunteers"

    volunteer_file = settings.BASE_DIR / "data" / "volunteers.csv"
    response_type = "First Mark"

    section_map = {
        "Buildings": "Buildings & Heating",
        "Buildings and Heating": "Buildings & Heating",
        "Planning": "Planning & Land Use",
        "Gov & Finance": "Governance & Finance",
        "Waste & Food": "Waste Reduction & Food",
        "Collab & Engagement": "Collaboration & Engagement",
        "Governance and Finance": "Governance & Finance",
        "Planning and Land Use": "Planning & Land Use",
        "Planning and Land use": "Planning & Land Use",
        "Waste Reduction and Food": "Waste Reduction & Food",
        "Collaboration and Engagement": "Collaboration & Engagement",
        "Waste reduction and food": "Waste Reduction & Food",
    }

    default_council_map = {
        "scorecards_volunteering": 6,
        "scorecards_assessor": 6,
        "local_climate_policy_programme": 15,
    }

    def add_arguments(self, parser):
        parser.add_argument(
            "-q", "--quiet", action="store_true", help="Silence progress bars."
        )

        parser.add_argument(
            "--file",
            action="store",
            required=True,
            help="CSV file containing the assignments",
        )

        parser.add_argument(
            "--col_names",
            action="store",
            help="CSV file containing use_cols and col_names args (one column for each)",
        )

        parser.add_argument(
            "--assignment_map",
            action="store",
            help="CSV file containing user_type, assignment_count columns to change default assignment counts",
        )

        parser.add_argument(
            "--authority_map",
            action="store",
            help="CSV file containing bad_name, good_name columns to map from bad councils names",
        )

        parser.add_argument(
            "--response_type",
            action="store",
            help="Stage to assign markers to",
        )

        parser.add_argument(
            "--session",
            action="store",
            required=True,
            help="Marking session to use assignements with",
        )

        parser.add_argument(
            "--assignment_count_in_data",
            action="store_true",
            help="use the section count in the csv and not the map",
        )

        parser.add_argument(
            "--preferred_councils",
            action="store_true",
            help="the data contains a column with councils to select from first, e.g Welsh councils.",
        )

        parser.add_argument(
            "--add_users", action="store_true", help="add users to database"
        )

        parser.add_argument(
            "--make_assignments", action="store_true", help="assign councils to users"
        )

        parser.add_argument(
            "--dry_run",
            action="store_true",
            help="run everything and then undo changes. Helpful to check if assigment weighting is good",
        )

        parser.add_argument(
            "--debug",
            action="store_true",
            help="spit out extra debug information",
        )

    def init(self, file, options):
        self.column_names = list(COLUMN_NAMES)
        self.usecols = list(USECOLS)
        self.debug = False

        if file is None:
            file = self.volunteer_file

        if options["assignment_count_in_data"]:
            self.column_names.append("assignment_count")
            self.usecols.append("How many sections?")

        if options["preferred_councils"]:
            self.column_names.append("preferred_councils")
            self.usecols.append("Nations/London")

        if options["debug"]:
            self.debug = True

    def get_df(self, filename):
        df = pd.read_csv(
            filename,
            usecols=self.usecols,
        )
        df.columns = self.column_names

        if "preferred_councils" in df.columns:
            df["preferred_councils"] = df["preferred_councils"].astype(str)

        return df

    def set_assignment_map(self, assignment_map):
        # this avoids namespace issues when testing
        self.num_council_map = copy(self.default_council_map)
        if assignment_map is not None:
            cols = pd.read_csv(assignment_map)
            for _, row in cols.iterrows():
                self.num_council_map[row.user_type] = row.assigned_count

    def set_cols(self, col_names):
        if col_names is not None:
            cols = pd.read_csv(col_names)
            self.usecols = cols.use_cols
            self.column_names = cols.col_names

    def set_authority_map(self, authority_map_file):
        self.authority_map = {}
        if authority_map_file:
            cols = pd.read_csv(authority_map_file)
            for _, row in cols.iterrows():
                self.authority_map[row.bad_name] = row.good_name

    def get_assignment_count(self, user_type, row, assignment_count_in_data):
        if assignment_count_in_data:
            try:
                count = int(row["assignment_count"])
            except ValueError:
                return None
            return count

        user_type = user_type.lower().replace(" ", "_")

        num_councils = self.num_council_map.get(user_type)
        return num_councils

    def add_users_and_assignments(self, df, response_type, session, rt, options):
        bad_councils = []
        for index, row in df.iterrows():
            if pd.isna(row["email"]):
                continue

            user_type = row["type_of_volunteering"]
            if user_type == "FOI_programme":
                continue

            if pd.isna(user_type):
                self.stdout.write(f"{YELLOW}No user type for {row['email']}{NOBOLD}")
                continue

            num_councils = self.get_assignment_count(
                user_type, row, options["assignment_count_in_data"]
            )
            if num_councils is None:
                self.stdout.write(
                    f"{YELLOW}Don't know how many councils to assign for {row['email']}{NOBOLD}"
                )
                continue

            email = row["email"]

            if options["add_users"] is True:
                u, _ = User.objects.update_or_create(
                    username=email,
                    defaults={
                        "is_active": True,
                        "email": email,
                        "first_name": row["first_name"],
                        "last_name": row["last_name"],
                    },
                )
                u.save()
                m, _ = Marker.objects.update_or_create(
                    user=u,
                    defaults={
                        "response_type": rt,
                        "send_welcome_email": True,
                    },
                )
                m.marking_session.set([session])
            else:
                try:
                    u = User.objects.get(username=email)
                except User.DoesNotExist:
                    self.stdout.write(
                        f"{YELLOW}No user found for {email}, not attempting assignment{NOBOLD}"
                    )
                    continue

            if not pd.isna(row["assigned_section"]):
                try:
                    title = self.section_map.get(
                        row["assigned_section"], row["assigned_section"]
                    )
                    s = Section.objects.get(title=title, marking_session=session)
                except Section.DoesNotExist:
                    self.stdout.write(
                        f"{RED}could not assign section for {row['email']}, no section {title}{NOBOLD}"
                    )
                    continue

            else:
                # self.stdout.write(f"no section assigned for {row['email']}")
                continue

            # CEUK staff/superusers can be assigned multiple sections
            if u.is_superuser or u.email.endswith("@climateemergency.uk"):
                existing_assignments = Assigned.objects.filter(
                    user=u, marking_session=session, response_type=rt, section=s
                )
            else:
                existing_assignments = Assigned.objects.filter(
                    user=u,
                    marking_session=session,
                    response_type=rt,
                )
            if existing_assignments.count() > 0:
                self.stdout.write(
                    f"{YELLOW}Existing assignments: {row['email']}{NOBOLD}"
                )
                continue

            councils = re.split("[,/]", row["council_area"])
            councils = [self.authority_map.get(c, c) for c in councils]

            own_council = PublicAuthority.objects.filter(name__icontains=councils[0])
            if len(councils) > 1:
                for council in councils[1:]:
                    own_council = own_council | PublicAuthority.objects.filter(
                        name__icontains=council
                    )

            if response_type != "First Mark":
                own_council = own_council | PublicAuthority.objects.filter(
                    id__in=Assigned.objects.filter(user=u, section=s)
                    .exclude(response_type=rt)
                    .values_list("authority")
                )

            if len(councils) > 0 and own_council.count() == 0:
                bad_councils.append((row["council_area"], row["email"]))
                self.stdout.write(
                    f"{RED}Bad council: {row['council_area']} (f{row['email']}){NOBOLD}"
                )
                continue

            assigned_councils = list(
                Assigned.objects.filter(
                    section=s, response_type=rt, authority__isnull=False
                ).values_list("authority_id", flat=True)
            )

            own_council_list = list(own_council.values_list("id", flat=True))
            assigned_councils = assigned_councils + own_council_list

            included_types = []
            included_countries = []
            if options["preferred_councils"]:
                preferred = row["preferred_councils"].split(",")

                for p in preferred:
                    if p.lower() in [
                        "scotland",
                        "england",
                        "wales",
                        "northern ireland",
                    ]:
                        included_countries.append(p.lower())
                    elif p == "London":
                        included_types.append("LBO")

            councils_to_assign = PublicAuthority.objects.filter(
                marking_session=session
            ).exclude(
                Q(id__in=assigned_councils) | Q(type="COMB") | Q(do_not_mark=True)
            )

            preferred_councils = councils_to_assign
            has_preferred = False
            if len(included_types) > 0 and len(included_countries) > 0:
                has_preferred = True
                preferred_councils = preferred_councils.filter(
                    Q(country__in=included_countries) | Q(type__in=included_types)
                )
            elif len(included_types) > 0:
                has_preferred = True
                preferred_councils = preferred_councils.filter(type__in=included_types)
            elif len(included_countries) > 0:
                has_preferred = True
                preferred_councils = preferred_councils.filter(
                    country__in=included_countries
                )

            if has_preferred:
                preferred_councils = preferred_councils[:num_councils]
                councils_left = num_councils - preferred_councils.count()
                councils_to_assign = councils_to_assign.exclude(
                    id__in=preferred_councils
                )[:councils_left]
                council_count = preferred_councils.count() + councils_to_assign.count()
            else:
                councils_to_assign = councils_to_assign[:num_councils]
                council_count = councils_to_assign.count()

            if council_count == 0:
                self.stdout.write(
                    f"{YELLOW}No councils left in {s.title} for {u.email}{NOBOLD}"
                )

            if options["make_assignments"] is True:
                if self.debug:
                    self.stdout.write(
                        f"{YELLOW}Assigning {council_count} councils in {s.title} to {u.email}{NOBOLD}"
                    )

                if has_preferred:
                    for council in preferred_councils:
                        a, created = Assigned.objects.update_or_create(
                            user=u,
                            section=s,
                            authority=council,
                            marking_session=session,
                            response_type=rt,
                        )
                for council in councils_to_assign:
                    a, created = Assigned.objects.update_or_create(
                        user=u,
                        section=s,
                        authority=council,
                        marking_session=session,
                        response_type=rt,
                    )

        return bad_councils

    def handle(
        self,
        quiet: bool = False,
        file: str = None,
        session: str = None,
        col_names: str = None,
        response_type: str = None,
        assignment_map: str = None,
        authority_map: str = None,
        *args,
        **options,
    ):
        self.init(file, options)
        self.set_cols(col_names)
        self.set_assignment_map(assignment_map)
        self.set_authority_map(authority_map)

        df = self.get_df(file)

        if response_type is None:
            response_type = self.response_type

        session = MarkingSession.objects.get(label=session)
        rt = ResponseType.objects.get(type=response_type)

        with transaction.atomic():
            bad_councils = self.add_users_and_assignments(
                df, response_type, session, rt, options
            )

            council_count = PublicAuthority.objects.filter(
                marking_session=session, do_not_mark=False
            ).count()
            for section in Section.objects.filter(marking_session=session).all():
                assigned = Assigned.objects.filter(
                    section=section, response_type=rt, marking_session=session
                ).count()
                if assigned != council_count:
                    self.stdout.write(
                        f"{RED}Not all councils assigned for {section.title} ({assigned}/{council_count}){NOBOLD}"
                    )
                else:
                    self.stdout.write(
                        f"{GREEN}All councils and sections assigned{NOBOLD}"
                    )

            volunteer_count = User.objects.filter(
                marker__marking_session=session, marker__response_type=rt
            ).count()
            assigned_count = (
                Assigned.objects.filter(response_type=rt, user__is_superuser=False)
                .distinct("user_id")
                .count()
            )

            self.stdout.write(
                f"{assigned_count}/{volunteer_count} users assigned marking"
            )

            if options["dry_run"]:
                transaction.set_rollback(True)

        if not options["add_users"]:
            self.stdout.write(
                f"{YELLOW}Dry run, no users added, call with --add_users to add users{NOBOLD}"
            )
        if not options["make_assignments"]:
            self.stdout.write(
                f"{YELLOW}Dry run, no assignments made, call with --make_assignments to make them{NOBOLD}"
            )

        if options["dry_run"]:
            self.stdout.write(
                f"{YELLOW}Dry run, no changes made, call without --dry_run to make changes{NOBOLD}"
            )

        if len(bad_councils):
            self.stdout.write("Bad councils are:")
            for c in bad_councils:
                self.stdout.write(f"{YELLOW}{c[0]}, {c[1]}{NOBOLD}")
