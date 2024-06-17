from django.conf import settings
from django.core.management.base import BaseCommand

import pandas as pd

from crowdsourcer.models import AuthorityData, PublicAuthority


class Command(BaseCommand):
    help = "import council minutes links"

    data_file = settings.BASE_DIR / "data" / "council_minutes.csv"

    def handle(self, *args, **kwargs):
        df = pd.read_csv(self.data_file)
        df = df.dropna(subset=["campaigns_lab_url"])

        for _, row in df.iterrows():
            gss = row["gss-code"]
            if not pd.isna(gss):
                try:
                    authority = PublicAuthority.objects.get(unique_id=gss)
                except PublicAuthority.DoesNotExist:
                    self.stderr.write(
                        f"could not find authority with GSS code {gss} ({row['official-name']}"
                    )
                    continue

                ad, _ = AuthorityData.objects.update_or_create(
                    authority=authority,
                    data_name="council_minutes",
                    defaults={
                        "data_value": row["campaigns_lab_url"],
                    },
                )
                print(authority.name)
