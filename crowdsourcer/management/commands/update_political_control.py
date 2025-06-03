from django.conf import settings

import pandas as pd

from crowdsourcer.import_utils import BaseImporter
from crowdsourcer.models import PublicAuthority


class Command(BaseImporter):
    help = "set up authorities and question groups"

    control_name_overrides = {
        "Shetland": "Shetland Islands Council",
        "Highland": "Comhairle nan Eilean Siar",
    }

    name_map = {
        "Southend-on-Sea Borough Council": "Southend-on-Sea City Council",
    }

    def add_arguments(self, parser):
        parser.add_argument(
            "-q", "--quiet", action="store_true", help="Silence progress bars."
        )

        parser.add_argument(
            "--file",
            action="store",
            required=True,
            help="File with the political control data",
        )

        parser.add_argument("--commit", action="store_true", help="commit things")

    def get_political_control(self, file):
        file = settings.BASE_DIR / file
        df = pd.read_csv(file)
        control = {}
        for _, row in df.iterrows():
            coalition = row["coalition"]
            if pd.isna(coalition):
                coalition = None
            control[row["lua code"]] = {
                "control": row["majority"],
                "coalition": coalition,
            }
            name = self.control_name_overrides.get(
                row["council name"], row["council name"] + " Council"
            )
            control[name] = {
                "control": row["majority"],
                "coalition": coalition,
            }
        return control

    def handle(
        self,
        quiet: bool = False,
        commit: bool = False,
        file: str = None,
        *args,
        **options
    ):
        political_control = self.get_political_control(file)

        self.quiet = quiet
        self.print_info("Importing political control")

        if not commit:
            self.print_info("call with --commit to save updates")

        with self.get_atomic_context(commit):
            for authority in PublicAuthority.objects.all():
                control = political_control.get(
                    authority.unique_id, political_control.get(authority.name, None)
                )

                if control is not None:
                    authority.political_control = control["control"]
                    authority.political_coalition = control["coalition"]
                    authority.save()
