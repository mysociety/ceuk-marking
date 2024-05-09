from django.core.management.base import BaseCommand

import pandas as pd

from crowdsourcer.models import (
    MarkingSession,
    PublicAuthority,
    QuestionGroup,
    ResponseType,
    Section,
)


class Command(BaseCommand):
    help = "set up authorities and question groups"

    groups = ["MP"]

    sections = [
        "Who Funds Them",
    ]

    session = "WhoFundsThem 2024"

    response_types = ["First Mark", "Right of Reply", "Audit"]

    def add_arguments(self, parser):
        parser.add_argument(
            "-q", "--quiet", action="store_true", help="Silence progress bars."
        )

    def get_group(self, mp):
        return QuestionGroup.objects.get(description="MP")

    def get_do_not_mark_list(self):
        df = pd.read_csv(self.do_not_mark_file)
        return list(df["gss-code"])

    def get_twfy_df(self):
        df = pd.read_csv("https://www.theyworkforyou.com/mps/?f=csv").rename(
            columns={"Person ID": "twfyid"}
        )

        return df

    def handle(self, quiet: bool = False, *args, **options):
        session, _ = MarkingSession.objects.get_or_create(
            label=self.session, defaults={"start_date": "2024-06-01"}
        )

        for section in self.sections:
            c, c = Section.objects.get_or_create(title=section, marking_session=session)

        for group in self.groups:
            g, c = QuestionGroup.objects.get_or_create(description=group)
            g.marking_session.set([session])

        for r_type in self.response_types:
            r, c = ResponseType.objects.get_or_create(type=r_type, priority=1)

        mps = self.get_twfy_df()

        if not quiet:
            print("Importing MPs")
        for _, mp in mps.iterrows():
            do_not_mark = False

            name = f"{mp['First name']} {mp['Last name']}"
            defaults = {
                "name": name,
                "questiongroup": self.get_group(mp),
                "do_not_mark": do_not_mark,
                "type": "MP",
            }

            a, created = PublicAuthority.objects.update_or_create(
                unique_id=mp["twfyid"],
                defaults=defaults,
            )
