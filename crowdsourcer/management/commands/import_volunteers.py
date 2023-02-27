import re

from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

import pandas as pd

from crowdsourcer.models import Assigned, PublicAuthority, Section

YELLOW = "\033[33m"
RED = "\033[31m"
GREEN = "\033[32m"
NOBOLD = "\033[0m"


class Command(BaseCommand):
    help = "import volunteers"

    volunteer_file = settings.BASE_DIR / "data" / "volunteers.xlsx"

    section_map = {
        "Buildings": "Buildings & Heating",
        "Planning": "Planning & Land Use",
        "Gov & Finance": "Governance & Finance",
        "Waste & Food": "Waste Reduction & Food",
        "Collab & Engagement": "Collaboration & Engagement",
    }

    num_council_map = {
        "scorecards_volunteering": 10,
        "local_climate_policy_programme": 20,
    }

    column_names = [
        "first_name",
        "last_name",
        "email",
        "council_area",
        "type_of_volunteering",
        "assigned_section",
    ]

    def add_arguments(self, parser):
        parser.add_argument(
            "-q", "--quiet", action="store_true", help="Silence progress bars."
        )

        parser.add_argument(
            "--add_users", action="store_true", help="add users to database"
        )

        parser.add_argument(
            "--make_assignments", action="store_true", help="assign councils to users"
        )

    def handle(self, quiet: bool = False, *args, **options):
        df = pd.read_excel(
            self.volunteer_file,
            usecols=[
                "First name",
                "Last name",
                "Email",
                "Council Area",
                "Type of Volunteering",
                "Assigned Section",
            ],
            sheet_name="Volunteer Recruitment Cohort 2",
        )
        df.columns = self.column_names

        for index, row in df.iterrows():
            if pd.isna(row["email"]):
                continue

            user_type = row["type_of_volunteering"]
            if user_type == "FOI_programme":
                continue

            if pd.isna(user_type):
                self.stdout.write(f"{YELLOW}No user type for {row['email']}{NOBOLD}")
                continue

            if options["add_users"] is True:
                u, created = User.objects.update_or_create(
                    username=row["email"],
                    defaults={
                        "email": row["email"],
                        "first_name": row["first_name"],
                        "last_name": row["last_name"],
                    },
                )
                u.save()
            else:
                try:
                    u = User.objects.get(username=row["email"])
                except User.DoesNotExist:
                    self.stdout.write(
                        f"{YELLOW}No user found for {row['email']}, not attempting assignment{NOBOLD}"
                    )
                    continue

            if not pd.isna(row["assigned_section"]):
                try:
                    title = self.section_map.get(
                        row["assigned_section"], row["assigned_section"]
                    )
                    s = Section.objects.get(title=title)
                except Section.DoesNotExist:
                    self.stdout.write(
                        f"{RED}could not assign section for {row['email']}, no section {title}{NOBOLD}"
                    )
                    continue

            else:
                # self.stdout.write(f"no section assigned for {row['email']}")
                continue

            existing_assignments = Assigned.objects.filter(user=u)
            if existing_assignments.count() > 0:
                self.stdout.write(
                    f"{YELLOW}Existing assignments: {row['email']}{NOBOLD}"
                )
                continue

            councils = re.split("[,/]", row["council_area"])

            own_council = PublicAuthority.objects.filter(name__icontains=councils[0])
            if len(councils) > 1:
                for council in councils[1:]:
                    own_council = own_council | PublicAuthority.objects.filter(
                        name__icontains=council
                    )

            if len(councils) > 0 and own_council.count() == 0:
                self.stdout.write(
                    f"{RED}Bad council: {row['council_area']} (f{row['email']}){NOBOLD}"
                )
                continue

            assigned_councils = list(
                Assigned.objects.filter(section=s, authority__isnull=False).values_list(
                    "authority_id", flat=True
                )
            )

            own_council_list = list(own_council.values_list("id", flat=True))
            assigned_councils = assigned_councils + own_council_list

            num_councils = self.num_council_map[user_type]

            councils_to_assign = PublicAuthority.objects.exclude(
                id__in=assigned_councils,
                type="COMB",
                do_not_mark=True,
            )[:num_councils]

            if councils_to_assign.count() == 0:
                self.stdout.write(
                    f"{YELLOW}No councils left in {s.title} for {u.email}{NOBOLD}"
                )

            if options["make_assignments"] is True:
                for council in councils_to_assign:
                    a, created = Assigned.objects.update_or_create(
                        user=u, section=s, authority=council
                    )

        council_count = PublicAuthority.objects.filter(do_not_mark=False).count()
        for section in Section.objects.all():
            assigned = Assigned.objects.filter(section=section).count()
            if assigned != council_count:
                self.stdout.write(
                    f"{RED}Not all councils assigned for {section.title} ({assigned}/{council_count}){NOBOLD}"
                )
            else:
                self.stdout.write(f"{GREEN}All councils and sections assigned{NOBOLD}")

        volunteer_count = User.objects.all().count()
        assigned_count = (
            Assigned.objects.filter(user__is_superuser=False)
            .distinct("user_id")
            .count()
        )

        self.stdout.write(f"{assigned_count}/{volunteer_count} users assigned marking")
        if not options["add_users"]:
            self.stdout.write(
                f"{YELLOW}Dry run, no users added, call with --add_users to add users{NOBOLD}"
            )
        if not options["make_assignments"]:
            self.stdout.write(
                f"{YELLOW}Dry run, no assignments made, call with --make_assignments to make them{NOBOLD}"
            )
