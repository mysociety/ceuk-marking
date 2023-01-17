from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

import pandas as pd

from crowdsourcer.models import Assigned, PublicAuthority, Section


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
        "address",
        "city",
        "state/province",
        "state/province_abbreviated",
        "zip_code",
        "country",
        "language",
        "mobile_number",
        "mobile_opt-in",
        "referrer_code",
        "source_code",
        "timestamp_(est)",
        "council_area",
        "experience",
        "group_interview_monday_16th_january",
        "group_interview_thursday_19th_january",
        "preferred_sections_biodiversity",
        "preferred_sections_buildings_&_heating",
        "preferred_sections_collaboration_&_engagement",
        "preferred_sections_gov_&_finance",
        "preferred_sections_no_preference",
        "preferred_sections_planning_&_land_use",
        "preferred_sections_transport",
        "preferred_sections_waste_reduction_&_food",
        "previous_volunteering_no",
        "previous_volunteering_yes",
        "training",
        "type_of_volunteering",
        "where_did_people_hear_about_volunteering",
        "why_do_you_want_to_volunteer",
        "attended_group_interview",
        "sent_signed_agreement",
        "assigned_section",
        "attended_scoring_training_part_1",
        "attended_scoring_training_part_2",
        "phone_number",
    ]

    def add_arguments(self, parser):
        parser.add_argument(
            "-q", "--quiet", action="store_true", help="Silence progress bars."
        )

    def handle(self, quiet: bool = False, *args, **options):
        df = pd.read_excel(
            self.volunteer_file,
            usecols=lambda name: "Unnamed" not in name,
        )
        df.columns = self.column_names

        for index, row in df.iterrows():
            user_type = row["type_of_volunteering"]
            if user_type == "FOI_programme":
                continue

            u, created = User.objects.update_or_create(
                username=row["email"],
                defaults={
                    "email": row["email"],
                    "first_name": row["first_name"],
                    "last_name": row["last_name"],
                },
            )
            u.save()

            if not pd.isna(row["assigned_section"]):
                try:
                    title = self.section_map.get(
                        row["assigned_section"], row["assigned_section"]
                    )
                    s = Section.objects.get(title=title)
                except Section.DoesNotExist:
                    self.stdout.write(
                        f"could not assign section for {row['email']}, no section {title}"
                    )
                    continue

            else:
                # self.stdout.write(f"no section assigned for {row['email']}")
                continue

            existing_assignments = Assigned.objects.filter(user=u)
            if existing_assignments.count() > 0:
                self.stdout.write(f"Existing assignments: {row['email']}")
                continue

            own_council = PublicAuthority.objects.filter(
                name__contains=row["council_area"]
            )
            if own_council.count() == 0:
                self.stdout.write(
                    f"Bad council: {row['council_area']} (f{row['email']})"
                )
                continue

            assigned_councils = list(
                Assigned.objects.filter(section=s, authority__isnull=False).values_list(
                    "authority_id", flat=True
                )
            )

            assigned_councils.append(own_council.values_list("id", flat=True)[:])

            num_councils = self.num_council_map[user_type]

            councils_to_assign = PublicAuthority.objects.exclude(
                id__in=assigned_councils
            )[:num_councils]

            if councils_to_assign.count() == 0:
                self.stdout.write(f"No councils left in {s.title} for {u.email}")

            for council in councils_to_assign:
                a, created = Assigned.objects.update_or_create(
                    user=u, section=s, authority=council
                )

            if index > 3:
                break

        council_count = PublicAuthority.objects.all().count()
        for section in Section.objects.all():
            assigned = Assigned.objects.filter(section=section).count()
            if assigned != council_count:
                self.stdout.write(
                    f"Not all councils assigned for {section.title} ({assigned}/{council_count})"
                )
