from django.conf import settings
from django.core.management.base import BaseCommand

import pandas as pd

from crowdsourcer.models import MarkingSession, ResponseType, Section


class Command(BaseCommand):
    help = "set up initial data for a session"

    # XXX
    # do_not_mark_file = settings.BASE_DIR / "data" / "do_not_mark.csv"

    groups = ["Single Tier", "District", "County", "Northern Ireland"]

    sections = None
    x = [
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

        parser.add_argument(
            "--session", action="store", help="Marking session to use questions with"
        )

        parser.add_argument(
            "--sections", action="store", help="csv file with list of sections"
        )

    def get_sections(self, **options):
        file = options.get("sections", None)

        if file is None:
            self.stderr.write("please supply a sections file name")
            return

        sections_file = settings.BASE_DIR / "data" / file

        if not sections_file.exists():
            self.stderr.write(f"file does not exist: {sections_file}")
            return

        df = pd.read_csv(sections_file)
        print(df)
        self.sections = []
        for _, row in df.iterrows():
            self.sections.append(row["Title"])

    def handle(self, quiet: bool = False, *args, **options):
        session_label = options.get("session", None)
        try:
            session = MarkingSession.objects.get(label=session_label)
        except MarkingSession.DoesNotExist:
            self.stderr.write(f"No session with that name: {session_label}")
            return

        self.get_sections(**options)

        if self.sections is None:
            return

        for section in self.sections:
            print(section)
            c, c = Section.objects.get_or_create(title=section, marking_session=session)

        for r_type in self.response_types:
            r, c = ResponseType.objects.get_or_create(type=r_type, priority=1)
