from django.core.management.base import BaseCommand

from crowdsourcer.models import PublicAuthority, QuestionGroup, ResponseType, Section
from utils import mapit


class Command(BaseCommand):
    help = "set up authorities and question groups"

    groups = ["Single Tier", "District", "County", "Northern Ireland"]

    sections = [
        "Buildings & Heating",
        "Transport",
        "Planning & Land Use",
        "Governance & Finance",
        "Biodiversity",
        "Collaboration & Engagement",
        "Waste Reduction & Food",
    ]

    response_types = ["First Mark", "Right of Reply", "Audit"]

    name_map = {
        "Southend-on-Sea Borough Council": "Southend-on-Sea City Council",
    }

    def add_arguments(self, parser):
        parser.add_argument(
            "-q", "--quiet", action="store_true", help="Silence progress bars."
        )

    def get_group(self, props):
        group = "District"

        print(props["name"], props["type"])
        if props["type"] == "LGD":
            group = "Northern Ireland"
        elif props["country"] == "W":
            group = "Single Tier"
        elif props["country"] == "S":
            group = "Single Tier"
        elif props["type"] in ["CC", "MTD", "LBO", "UTA"]:
            group = "Single Tier"
        elif props["type"] in ["CTY"]:
            group = "County"

        g = QuestionGroup.objects.get(description=group)
        return g

    def handle(self, quiet: bool = False, *args, **options):
        for section in self.sections:
            c, c = Section.objects.get_or_create(title=section)

        for group in self.groups:
            g, c = QuestionGroup.objects.get_or_create(description=group)

        for r_type in self.response_types:
            r, c = ResponseType.objects.get_or_create(type=r_type, priority=1)

        mapit_client = mapit.MapIt()
        areas = mapit_client.areas_of_type(
            ["CTY", "LBO", "NMD", "UTA", "LGD", "CC", "DIS", "MTD"]
        )

        if not quiet:
            print("Importing Areas")
        for area in areas:
            a, created = PublicAuthority.objects.update_or_create(
                unique_id=area["codes"]["gss"],
                defaults={
                    "name": self.name_map.get(area["name"], area["name"]),
                    "questiongroup": self.get_group(area),
                },
            )
