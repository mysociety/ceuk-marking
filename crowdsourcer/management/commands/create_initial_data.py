from django.conf import settings
from django.core.management.base import BaseCommand

import pandas as pd

from crowdsourcer.models import PublicAuthority, QuestionGroup, ResponseType, Section
from utils import mapit


class Command(BaseCommand):
    help = "set up authorities and question groups"

    do_not_mark_file = settings.BASE_DIR / "data" / "do_not_mark.csv"
    political_control_file = settings.BASE_DIR / "data" / "opencouncildata_councils.csv"

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

    control_name_overrides = {
        "Shetland": "Shetland Islands Council",
        "Highland": "Comhairle nan Eilean Siar",
    }

    response_types = ["First Mark", "Right of Reply", "Audit"]

    name_map = {
        "Southend-on-Sea Borough Council": "Southend-on-Sea City Council",
    }

    def add_arguments(self, parser):
        parser.add_argument(
            "-q", "--quiet", action="store_true", help="Silence progress bars."
        )

    def get_do_not_mark_list(self):
        df = pd.read_csv(self.do_not_mark_file)
        return list(df["gss-code"])

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

    def get_political_control(self):
        df = pd.read_csv(self.political_control_file)
        control = {}
        for _, row in df.iterrows():
            coalition = row["coalition"]
            if pd.isna(coalition):
                coalition = None
            control[row["ons code"]] = {
                "control": row["majority"],
                "coalition": coalition,
            }
            name = self.control_name_overrides.get(
                row["name"], row["name"] + " Council"
            )
            control[name] = {
                "control": row["majority"],
                "coalition": coalition,
            }
        return control

    def handle(self, quiet: bool = False, *args, **options):
        do_not_mark_list = self.get_do_not_mark_list()

        for section in self.sections:
            c, c = Section.objects.get_or_create(title=section)

        for group in self.groups:
            g, c = QuestionGroup.objects.get_or_create(description=group)

        for r_type in self.response_types:
            r, c = ResponseType.objects.get_or_create(type=r_type, priority=1)

        mapit_client = mapit.MapIt()
        areas = mapit_client.areas_of_type(
            ["CTY", "LBO", "NMD", "UTA", "LGD", "CC", "DIS", "MTD", "COI"]
        )

        political_control = self.get_political_control()

        if not quiet:
            print("Importing Areas")
        for area in areas:
            do_not_mark = False
            if area["codes"]["gss"] in do_not_mark_list:
                do_not_mark = True

            defaults = {
                "name": self.name_map.get(area["name"], area["name"]),
                "questiongroup": self.get_group(area),
                "do_not_mark": do_not_mark,
                "type": area["type"],
                "country": area["country_name"].lower(),
            }
            control = political_control.get(
                area["codes"]["gss"], political_control.get(defaults["name"], None)
            )
            if control is not None:
                defaults["political_control"] = control["control"]
                defaults["political_coalition"] = control["coalition"]

            a, created = PublicAuthority.objects.update_or_create(
                unique_id=area["codes"]["gss"],
                defaults=defaults,
            )
