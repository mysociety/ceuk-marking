from django.core.management.base import BaseCommand

import pandas as pd


class Command(BaseCommand):
    help = "create list of all broken evidence links"

    def add_arguments(self, parser):
        parser.add_argument(
            "--links",
            action="store",
            required=True,
            help="CSV file with list of link response codes",
        )

    def handle(self, *args, **kwargs):
        file = kwargs["links"]

        df = pd.read_csv(file)
        df = df.dropna(how="any")
        df = df.loc[~df["status_code"].isin([200, 301, 302])]

        df.to_csv("data/broken_links.csv")
