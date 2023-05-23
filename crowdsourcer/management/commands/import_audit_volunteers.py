import re

from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db.models import Q

import pandas as pd

from crowdsourcer.models import Assigned, PublicAuthority, ResponseType, Section

YELLOW = "\033[33m"
RED = "\033[31m"
GREEN = "\033[32m"
NOBOLD = "\033[0m"

FULL_AUDIT_NUM = 40
HALF_AUDIT_NUM = 20


class Command(BaseCommand):
    help = "import volunteers"

    volunteer_file = settings.BASE_DIR / "data" / "audit_volunteers.xlsx"

    section_map = {
        "Buildings": "Buildings & Heating",
        "Planning": "Planning & Land Use",
        "Gov & Finance": "Governance & Finance",
        "Waste & Food": "Waste Reduction & Food",
        "Collab & Engagement": "Collaboration & Engagement",
    }

    full_num_council_map = {
        "Transport": 30,
        "Waste Reduction & Food": 33,
    }
    half_num_council_map = {
        "Transport": 13,
        "Waste Reduction & Food": 15,
    }

    column_names = [
        "email",
        "first_name",
        "last_name",
        "council_area",
        "assigned_section",
        "second_section",
        "audit_level",
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

    def get_councils_to_assign(self, section, row, user, num_councils):
        if not pd.isna(section):
            try:
                title = self.section_map.get(section, section)
                s = Section.objects.get(title=title)
            except Section.DoesNotExist:
                self.stdout.write(
                    f"{RED}could not assign section for {row['email']}, no section {title}{NOBOLD}"
                )
                return None, None

        else:
            # self.stdout.write(f"no section assigned for {row['email']}")
            return None, None

        existing_assignments = Assigned.objects.filter(
            user=user, response_type=self.audit_rt
        )
        if existing_assignments.count() > 0:
            self.stdout.write(f"{YELLOW}Existing assignments: {row['email']}{NOBOLD}")
            return None, None

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
            return None, None

        first_mark_councils = Assigned.objects.filter(
            user=user,
            response_type=self.first_mark_rt,
            section=s,
            authority__isnull=False,
        ).values_list("authority_id", flat=True)

        assigned_councils = list(
            Assigned.objects.filter(section=s, authority__isnull=False).values_list(
                "authority_id", flat=True
            )
        )

        own_council_list = list(own_council.values_list("id", flat=True))
        assigned_councils = (
            assigned_councils + own_council_list + list(first_mark_councils)
        )

        num_councils = self.full_num_council_map.get(s.title, num_councils)
        if str(row["audit_level"]).find("20") != -1:
            num_councils = self.half_num_council_map.get(s.title, HALF_AUDIT_NUM)

        councils_to_assign = PublicAuthority.objects.exclude(
            Q(id__in=assigned_councils) | Q(type="COMB") | Q(do_not_mark=True)
        )[:num_councils]

        if councils_to_assign.count() == 0:
            self.stdout.write(
                f"{YELLOW}No councils left in {s.title} for {user.email}{NOBOLD}"
            )

        return councils_to_assign, s

    def handle(self, quiet: bool = False, *args, **options):
        df = pd.read_excel(
            self.volunteer_file,
            usecols=[
                "First Name",
                "Surname",
                "Email",
                "Council Area",
                "Section",
                "Second Section?",
                "How many sections assigned?",
            ],
            sheet_name="Auditors",
        )
        df.columns = self.column_names

        self.audit_rt = ResponseType.objects.get(type="Audit")
        self.first_mark_rt = ResponseType.objects.get(type="First Mark")

        for index, row in df.iterrows():
            if pd.isna(row["email"]):
                continue
            if row["email"] == "Dropped out":
                break
            try:
                audit_level = int(row["audit_level"])
            except ValueError:
                self.stdout.write(
                    f"{YELLOW}No audit level for for {row['email']}, not attempting assignment{NOBOLD}"
                )
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
            for section in [row["assigned_section"], row["second_section"]]:
                councils_to_assign, s = self.get_councils_to_assign(
                    section, row, u, audit_level
                )

                if councils_to_assign is None:
                    continue

                if options["make_assignments"] is True:
                    for council in councils_to_assign:
                        a, created = Assigned.objects.update_or_create(
                            user=u,
                            section=s,
                            authority=council,
                            response_type=self.audit_rt,
                        )

        council_count = (
            PublicAuthority.objects.filter(do_not_mark=False)
            .exclude(type="COMB")
            .count()
        )
        ca_council_count = (
            PublicAuthority.objects.filter(do_not_mark=False)
            .filter(type="COMB")
            .count()
        )
        for section in Section.objects.all():
            council_comaparison = council_count
            if section.title.find("(CA)") >= 0:
                council_comaparison = ca_council_count
            assigned = Assigned.objects.filter(section=section).count()
            if assigned != council_comaparison:
                self.stdout.write(
                    f"{RED}Not all councils assigned for {section.title} ({assigned}/{council_comaparison}){NOBOLD}"
                )
            else:
                self.stdout.write(
                    f"{GREEN}All councils assigned for {section.title}{NOBOLD}"
                )

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
