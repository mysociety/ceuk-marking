from django.conf import settings
from django.core.management.base import BaseCommand

import pandas as pd

from crowdsourcer.models import PublicAuthority


class Command(BaseCommand):
    help = "add websites to authority"

    csv = settings.BASE_DIR / "data" / "council_websites.csv"

    def handle(self, quiet: bool = False, *args, **options):
        df = pd.read_csv(self.csv)

        for index, row in df.iterrows():
            try:
                authority = PublicAuthority.objects.get(name=row["council"])
            except PublicAuthority.DoesNotExist:
                continue

            authority.website = row["url"]
            authority.save()
