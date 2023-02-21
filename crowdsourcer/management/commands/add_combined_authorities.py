from django.conf import settings
from django.core.management.base import BaseCommand

import pandas as pd

from crowdsourcer.models import PublicAuthority, QuestionGroup, Section


class Command(BaseCommand):
    help = "set up combined authorities"

    authority_file = settings.BASE_DIR / "data" / "uk_local_authorities_current.csv"

    sections = [
        "Buildings & Heating & Green Skills (CA)",
        "Transport (CA)",
        "Planning & Biodiversity (CA)",
        "Governance & Finance (CA)",
        "Collaboration & Engagement (CA)",
    ]

    def handle(self, *args, **options):
        print("Creating groups and sections")
        group, _ = QuestionGroup.objects.get_or_create(description="Combined Authority")

        for section in self.sections:
            c, c = Section.objects.get_or_create(title=section)

        df = pd.read_csv(self.authority_file)

        print("Importing Combined Authorities")
        for _, row in df.iterrows():
            if row["local-authority-type"] not in ["COMB", "SRA"]:
                continue

            a, _ = PublicAuthority.objects.update_or_create(
                unique_id=row["gss-code"],
                defaults={
                    "name": row["official-name"],
                    "questiongroup": group,
                },
            )
