from typing import Optional

import pandas as pd

from crowdsourcer.import_utils import BaseImporter
from crowdsourcer.models import (
    MarkingSession,
    Response,
)


class Command(BaseImporter):
    help = "replace FOI urls"
    url_map = {}

    def add_arguments(self, parser):
        parser.add_argument(
            "--session",
            action="store",
            required=True,
            help="marking session",
        )

        parser.add_argument(
            "--url_file",
            action="store",
            required=True,
            help="CSV with urls to replace along with replacements",
        )
        parser.add_argument("--commit", action="store_true", help="commit things")

        parser.add_argument("--quiet", action="store_true", help="output less")

    def get_marking_session(self, label) -> Optional[MarkingSession]:
        try:
            ms = MarkingSession.objects.get(label=label)
        except MarkingSession.DoesNotExist:
            return None

        return ms

    def populate_url_map(self):
        df = pd.read_csv(
            self.url_file,
        )

        for _, row in df.iterrows():
            self.url_map[row["request_url"]] = row["new_private_link"]

    def get_responses_to_update(self) -> Optional[Response]:
        old_urls = self.url_map.keys()
        responses = Response.objects.filter(
            question__section__marking_session=self.ms,
            evidence__in=old_urls,
        ).select_related("question", "question__section", "authority")
        return responses

    def update_responses(self, responses):
        for r in responses:
            self.print_debug(
                f"{r.question.section} {r.question.number_and_part} {r.authority}: replacing {r.evidence} with {self.url_map[r.evidence]}"
            )
            r.evidence = self.url_map[r.evidence]
            r.save()

    def update_urls(self):
        responses = self.get_responses_to_update()
        self.print_info(f"Replacing urls in {responses.count()} responses")
        self.update_responses(responses)

    def handle(
        self,
        url_file: str,
        session: str,
        commit: bool = False,
        quiet: bool = False,
        *args,
        **kwargs,
    ):
        self.commit = commit
        self.url_file = url_file
        self.quiet = quiet

        self.ms = self.get_marking_session(session)
        if self.ms is None:
            self.print_error(f"No such session {session}")
            return

        self.populate_url_map()

        if not self.commit:
            self.print_info("call with --commit to save updates")

        with self.get_atomic_context(self.commit):
            self.update_urls()
