import pandas as pd

from crowdsourcer.import_utils import BaseTransactionCommand
from crowdsourcer.models import PublicAuthority, QuestionGroup
from utils import mapit


class Command(BaseTransactionCommand):
    help = "update council list to include new councils"

    groups = ["Single Tier", "District", "County", "Northern Ireland"]

    name_map = {}

    def add_arguments(self, parser):
        parser.add_argument(
            "-q", "--quiet", action="store_true", help="Silence progress bars."
        )

        parser.add_argument(
            "-t",
            "--types",
            action="store",
            help="Comma separated list of council types",
        )

        parser.add_argument(
            "--csv",
            action="store",
            help="file to output csv of councils",
        )

        parser.add_argument("--commit", action="store_true", help="commit things")

    def get_group(self, props):
        group = "District"

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

    def handle(
        self,
        quiet: bool = False,
        commit: bool = False,
        types: str = "CTY,LBO,NMD,UTA,LGD,CC,DIS,MTD,COI",
        csv: str = "",
        *args,
        **options,
    ):
        self.commit = commit

        if not self.commit:
            self.stdout.write("call with --commit to save updates")

        council_types = types.split(",")

        if not quiet:
            self.stdout.write(types)

        mapit_client = mapit.MapIt()
        areas = mapit_client.areas_of_type(council_types)

        if not quiet:
            self.stdout.write("Importing Areas")

        existing = []
        added = []
        all_councils = []
        with self.get_atomic_context(self.commit):
            for area in areas:
                defaults = {
                    "name": self.name_map.get(area["name"], area["name"]),
                    "questiongroup": self.get_group(area),
                    "type": area["type"],
                    "country": area["country_name"].lower(),
                }

                a, created = PublicAuthority.objects.get_or_create(
                    unique_id=area["codes"]["gss"],
                    defaults=defaults,
                )

                if csv != "":
                    all_councils.append([a.name, a.unique_id])

                if created:
                    added.append(defaults["name"])
                else:
                    existing.append(defaults["name"])

        if not quiet:
            added.sort()
            existing.sort()

            self.stdout.write("Existing councils")
            for council in existing:
                self.stdout.write(council)

            if added:
                self.stdout.write()
                self.stdout.write("New councils")
                for council in added:
                    self.stdout.write(council)

        if csv != "":
            df = pd.DataFrame(all_councils, None, ["council", "gssNumber"])
            df.to_csv(csv)
