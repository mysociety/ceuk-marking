from collections.abc import Generator
from contextlib import contextmanager

from django.core.management.base import BaseCommand
from django.db.transaction import atomic

import pandas as pd
from mysoc_dataset import get_dataset_url

from crowdsourcer.models import MarkingSession, PublicAuthority, ResponseType


# from https://adamj.eu/tech/2022/10/13/dry-run-mode-for-data-imports-in-django/
class DoRollback(Exception):
    pass


@contextmanager
def rollback_atomic() -> Generator[None, None, None]:
    try:
        with atomic():
            yield
            raise DoRollback()
    except DoRollback:
        pass


class BaseImporter(BaseCommand):
    YELLOW = "\033[33m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    NOBOLD = "\033[0m"

    def print_msg(self, message, level=2, type="info"):
        if self.quiet and level > 1:
            return

        colour = self.YELLOW
        out = self.stdout

        if type == "success":
            colour = self.GREEN
        elif type == "error":
            out = self.stderr
            colour = self.RED

        message = f"{colour}{message}{self.NOBOLD}"
        out.write(message)

    def print_error(self, message):
        self.print_msg(message, level=1, type="error")

    def print_success(self, message):
        self.print_msg(message, level=1, type="success")

    def print_info(self, message):
        self.print_msg(message, level=1)

    def print_debug(self, message):
        self.print_msg(message, type="debug")

    def get_council_lookup(self):
        url = get_dataset_url(
            repo_name="uk_local_authority_names_and_codes",
            package_name="uk_la_future",
            version_name="latest",
            file_name="uk_local_authorities_future.csv",
            done_survey=True,
        )
        df = pd.read_csv(url)

        lookup = {}
        for _, row in df.iterrows():
            gss = row["gss-code"]
            lookup[row["nice-name"].replace(" ", "-").lower()] = gss
            lookup[row["nice-name"]] = gss
            lookup[row["official-name"]] = gss

        return lookup

    def get_authority(self, authority, ms):
        # orig_authority = authority
        authority = self.authority_map.get(authority, authority)

        gss = None
        if authority in self.council_lookup:
            gss = self.council_lookup[authority]
        else:
            for banned in [
                "Borough",
                "City",
                "Council",
                "County",
                "District",
                "Metropolitan",
            ]:
                authority = authority.replace(banned, "")
            authority = authority.replace("&", "and")
            authority = authority.strip().replace(" ", "-").lower()
            if authority in self.council_lookup:
                gss = self.council_lookup[authority]

        try:
            authority = PublicAuthority.objects.get(unique_id=gss, marking_session=ms)
        except PublicAuthority.DoesNotExist:
            return None

        return authority

    def set_authority_map(self, authority_map_file):
        self.authority_map = {}
        if authority_map_file:
            cols = pd.read_csv(authority_map_file)
            for _, row in cols.iterrows():
                self.authority_map[row.bad_name] = row.good_name

    def get_stage_and_session(self, stage, session):
        try:
            rt = ResponseType.objects.get(type=stage)
        except ResponseType.DoesNotExist:
            self.print_error(f"No such ResponseType {stage}")

        try:
            ms = MarkingSession.objects.get(label=session)
        except MarkingSession.DoesNotExist:
            self.print_error(f"No such Marking Session {session}")

        return (rt, ms)

    def get_atomic_context(self, commit):
        if commit:
            atomic_context = atomic()
        else:
            atomic_context = rollback_atomic()

        return atomic_context
