from django.conf import settings
from django.core.management.base import BaseCommand

import pandas as pd

from crowdsourcer.models import PublicAuthority

YELLOW = "\033[33m"
RED = "\033[31m"
GREEN = "\033[32m"
NOBOLD = "\033[0m"


class Command(BaseCommand):
    help = "import councils"

    officers = settings.BASE_DIR / "data" / "comeval_officers.csv"
    preferred = settings.BASE_DIR / "data" / "preferred_contacts.csv"
    merged = settings.BASE_DIR / "data" / "merged_contacts.csv"

    def add_arguments(self, parser):
        parser.add_argument(
            "-q", "--quiet", action="store_true", help="Silence progress bars."
        )

        parser.add_argument(
            "--add_users", action="store_true", help="add users to database"
        )

    def handle(self, quiet: bool = False, *args, **options):
        df = pd.read_csv(
            self.officers,
            usecols=[
                "firstName",
                "surname",
                "council",
                "official-name",
                "councilInternalName",
                "gssNumber",
                "email",
            ],
        )

        pref_df = pd.read_csv(self.preferred)

        prefs = {}
        for index, row in pref_df.iterrows():
            prefs[row["Council"].lower()] = row

        seen = {}

        out = []
        for index, row in df.iterrows():
            pref_name = None
            for name in [
                row["councilInternalName"],
                row["official-name"],
                row["council"],
            ]:
                name = str(name).lower()
                if prefs.get(name, None) is not None:
                    pref_name = name

            if pd.isna(row["email"]) or pd.isna(row["gssNumber"]):
                if pref_name is not None:
                    prefs[pref_name]["no_comeval_email"] = True
                continue

            try:
                council = PublicAuthority.objects.get(unique_id=row["gssNumber"])
            except PublicAuthority.DoesNotExist:
                print(
                    f"No council with GSS of {row['gssNumber']}, {row['council']} found"
                )
                continue

            if seen.get(row["gssNumber"], None) is not None:
                continue

            seen[row["gssNumber"]] = 1

            if council.do_not_mark:
                continue

            if pref_name is None and prefs.get(council.name, None) is not None:
                pref_name = council.name

            if pref_name is not None:
                p = prefs[pref_name]
                row["firstName"] = p["First Name"]
                row["surname"] = p["Surname"]
                row["email"] = p["Preferred Email"]

                prefs[pref_name]["matched"] = 1

            out.append(row)

        for pref in prefs.values():
            if pref.get("matched", None) is None and not pref.get(
                "no_comeval_email", False
            ):
                print(f"no pref match for {pref['Council']}")
            if pref.get("matched", None) is None and pref.get(
                "no_comeval_email", False
            ):
                try:
                    council = PublicAuthority.objects.get(name=pref["Council"])
                except PublicAuthority.DoesNotExist:
                    print(f"No council with name of {p['Council']} found")
                    continue

                out.append(
                    pd.Series(
                        {
                            "gssNumber": council.unique_id,
                            "firstName": pref["First Name"],
                            "surname": pref["Surname"],
                            "email": pref["Preferred Email"],
                            "councilInternalName": "",
                            "council": council.name,
                            "official-name": "",
                        }
                    )
                )

        out_df = pd.DataFrame(out)
        out_df.to_csv(self.merged)
