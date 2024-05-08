from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils.text import slugify

import pandas as pd

from crowdsourcer.models import MarkingSession
from crowdsourcer.scoring import get_scoring_object


class Command(BaseCommand):
    help = "export totals"

    def make_file_names(self, session):
        session_slug = slugify(session)
        base_dir = settings.BASE_DIR / "data" / session_slug
        base_dir.mkdir(mode=0o755, exist_ok=True)

        self.total_scores_file = base_dir / "raw_maxes.csv"
        self.w_total_scores_file = base_dir / "weighted_maxes.csv"

    def write_files(self, totals, w_totals):
        df = pd.DataFrame.from_records(totals)
        df.to_csv(self.total_scores_file)

        df = pd.DataFrame.from_records(w_totals)
        df.to_csv(self.w_total_scores_file)

    def add_arguments(self, parser):
        parser.add_argument(
            "--session", action="store", help="Name of the marking session to use"
        )

    def handle(
        self,
        *args,
        **options,
    ):

        session_label = options["session"]
        try:
            session = MarkingSession.objects.get(label=session_label)
        except MarkingSession.DoesNotExist:
            self.stderr.write(f"No such session: {session_label}")
            sessions = [s.label for s in MarkingSession.objects.all()]
            self.stderr.write(f"Available sessions are {sessions}")
            return

        self.session = session
        self.make_file_names(session_label)

        scoring = get_scoring_object(session)

        groups = [
            "Single Tier",
            "District",
            "County",
            "Northern Ireland",
            "Combined Authority",
        ]
        raw_maxes = [["section", "single tier", "district", "county", "NI", "CA"]]
        weighted_maxes = [["section", "single tier", "district", "county", "NI", "CA"]]

        for section in scoring["section_maxes"].keys():
            w_maxes = scoring["section_weighted_maxes"][section]
            r_maxes = scoring["section_maxes"][section]

            raw = [r_maxes[g] for g in groups]
            weighted = [w_maxes[g] for g in groups]

            raw.insert(0, section)
            weighted.insert(0, section)

            raw_maxes.append(raw)
            weighted_maxes.append(weighted)

        self.write_files(raw_maxes, weighted_maxes)
