from django.conf import settings

import pandas as pd


def get_bad_urls():
    file = settings.BASE_DIR / "data" / "broken_links.csv"
    if file.exists():
        df = pd.read_csv(file)

        links = df["url"]

        return set(links)

    return []


def check_if_url_bad(url):
    bad_urls = get_bad_urls()

    if url in bad_urls:
        return True

    return False
