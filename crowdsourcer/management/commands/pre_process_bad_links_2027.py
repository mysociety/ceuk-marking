import re

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
        df = df.astype({"validated_url": str})

        link_parts_re = re.compile(r".*\((?P<code>\d+)\):\s+(?P<url>https?:[^ ]*)")

        bad_links = []
        for _, row in df.iterrows():
            links = row["validated_url"].split("|")
            for link in links:
                parts = re.search(link_parts_re, link)
                if parts is not None and parts.group("code") in ["404", "410"]:
                    bad_links.append([parts.group("url"), parts.group("code")])

        processed = pd.DataFrame(data=bad_links, columns=["url", "status_code"])
        processed.to_csv("data/2027/broken_links.csv")
