from django.conf import settings
from django.core.management.base import BaseCommand

import pandas as pd


class Command(BaseCommand):
    help = "show housing score changes"

    data_dir = settings.BASE_DIR / "data" / "housing_fix_details"
    fixed_data = data_dir / "all_section_scores.csv"
    old_data = data_dir / "all_section_scores_pre.csv"
    diff_data = data_dir / "differences.csv"

    def get_council_scores(self, df):
        councils = {}

        for _, row in df.iterrows():
            councils[row["council"]] = {
                "section_score": row["Buildings & Heating"],
                "overall_score": row["weighted_total"],
            }

        return councils

    def get_diffs(self, old, fixed):
        diffs = []

        headers = [
            "council",
            "old section score",
            "new section score",
            "diff",
            "old overall score",
            "new overall score",
            "diff",
            "now high performer",
        ]

        diffs.append(headers)

        for council, old_score in old.items():
            if pd.isna(old_score["section_score"]):
                continue

            if fixed.get(council, None) is not None:
                new_score = fixed[council]
                if (
                    old_score["section_score"] != new_score["section_score"]
                    or old_score["overall_score"] != new_score["overall_score"]
                ):
                    section_diff = (
                        new_score["section_score"] - old_score["section_score"]
                    )
                    overall_diff = (
                        new_score["overall_score"] - old_score["overall_score"]
                    )

                    is_high = False
                    if (
                        old_score["section_score"] < 0.8
                        and new_score["section_score"] >= 0.8
                    ):
                        is_high = True

                    diffs.append(
                        [
                            council,
                            old_score["section_score"],
                            new_score["section_score"],
                            round(section_diff, 2),
                            old_score["overall_score"],
                            new_score["overall_score"],
                            round(overall_diff, 2),
                            is_high,
                        ]
                    )

        return diffs

    def handle(self, *args, **options):
        old_df = pd.read_csv(self.old_data)
        fixed_df = pd.read_csv(self.fixed_data)

        old = self.get_council_scores(old_df)
        fixed = self.get_council_scores(fixed_df)

        diffs = self.get_diffs(old, fixed)

        diff_df = pd.DataFrame(diffs, index=None)
        diff_df = diff_df.rename(columns=diff_df.iloc[0]).drop(diff_df.index[0])
        diff_df = diff_df.set_index("council")
        diff_df.to_csv(self.diff_data)
