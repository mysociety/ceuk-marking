from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils.text import slugify

import pandas as pd

from crowdsourcer.models import MarkingSession
from crowdsourcer.scoring import get_scoring_object


class Command(BaseCommand):
    help = "export raw and weighted section scores"

    def make_file_names(self, session):
        session_slug = slugify(session)
        base_dir = settings.BASE_DIR / "data" / session_slug
        base_dir.mkdir(mode=0o755, exist_ok=True)

        self.section_scores_file = base_dir / "raw_and_weighted_sections.csv"

    def write_files(self, cols, totals):
        df = pd.DataFrame.from_records(totals, columns=cols)
        df.to_csv(self.section_scores_file)

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

        rows = []
        cols = [
            "council",
            "country",
            "type",
            "political_control",
            "section",
            "raw score",
            "raw max",
            "raw weighted",
            "weighted max",
            "weighted score",
            "section weighted score",
            "total",
        ]

        for council, council_score in scoring["section_totals"].items():
            country = scoring["council_countries"][council]
            council_type = scoring["council_type"][council]
            control = scoring["council_control"][council]
            for section, scores in council_score.items():
                row = [
                    council,
                    country,
                    council_type,
                    control,
                    section,
                    scores["raw"],
                    scoring["council_maxes"][council]["raw"][section][
                        scoring["council_groups"][council]
                    ],
                    scores["raw_weighted"],
                    scoring["council_maxes"][council]["weighted"][section][
                        scoring["council_groups"][council]
                    ],
                    scores["unweighted_percentage"],
                    scores["weighted"],
                    "",
                ]

                rows.append(row)
            total = scoring["council_totals"][council]["weighted_total"]
            rows.append(
                [
                    council,
                    country,
                    council_type,
                    control,
                    "Total",
                    "-",
                    "-",
                    "-",
                    "-",
                    "-",
                    "-",
                    f"{total:.2f}",
                ]
            )

        self.write_files(cols, rows)
