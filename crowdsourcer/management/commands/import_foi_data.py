from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

import pandas as pd
from mysoc_dataset import get_dataset_url

from crowdsourcer.models import (
    Option,
    PublicAuthority,
    Question,
    Response,
    ResponseType,
    Section,
)


class Command(BaseCommand):
    help = "import FOI data"

    sheet_map = None
    use_csvs = False

    foi_file = settings.BASE_DIR / "data" / "foi_data.xlsx"
    foi_dir = settings.BASE_DIR / "data" / "foi_csvs"
    url_map_file = (
        settings.BASE_DIR / "data" / "ceuk-requests-with-private-link-url.csv"
    )

    combined_foi_file = settings.BASE_DIR / "data" / "combined_foi_data.xlsx"

    warnings = []
    url_map = {}

    # get round limits on length of sheet names
    non_combined_sheet_map = {
        "Biodiversity Q8": {
            "section": "Biodiversity",
            "question": 8,
            "type": "yes_no",
            "twfy-project": 19,
        },
        "B&H Q2": {
            "section": "Buildings & Heating",
            "question": 2,
            "type": "tiered",
            "twfy-project": 12,
        },
        "B&H Q3": {
            "section": "Buildings & Heating",
            "question": 3,
            "type": "tiered",
            "twfy-project": 13,
        },
        "B&H Q6": {
            "section": "Buildings & Heating",
            "question": 6,
            "type": "yes_no",
            "twfy-project": 18,
        },
        "B&H Q8": {
            "section": "Buildings & Heating",
            "question": 8,
            "type": "tiered",
            "twfy-project": 17,
        },
        "C&E Q3": {
            "section": "Buildings & Heating",
            "question": 8,
            "type": "yes_no",
            "twfy-project": 16,
        },
        "G&F Q8": {
            "section": "Governance & Finance",
            "question": 8,
            "type": "yes_no",
            "twfy-project": 14,
        },
        "G&F Q9": {
            "section": "Governance & Finance",
            "question": 9,
            "type": "yes_no",
            "twfy-project": 11,
        },
        "Planning 11": {
            "section": "Planning & Land Use",
            "question": 11,
            "type": "yes_no",
            "twfy-project": 21,
        },
        "Transport 11i": {
            "section": "Transport",
            "question": 11,
            "type": "yes_no",
            "twfy-project": 15,
        },
        "Transport 11ii": {
            "section": "Transport",
            "question": 11,
            "type": "yes_no",
            "twfy-project": 20,
        },
    }

    combined_sheet_map = {
        "Collaboration & Engagement 3A": {
            "section": "Collaboration & Engagement (CA)",
            "question": 3,
            "question_part": "a",
            "type": "yes_no",
        },
        "Buildings & Heating & Skills 1": {
            "section": "Buildings & Heating & Green Skills (CA)",
            "question": 1,
            "type": "tiered",
        },
        "Buildings & Heating & Skills 9a": {
            "sheet": "Buildings & Heating & Skills 9",
            "section": "Buildings & Heating & Green Skills (CA)",
            "question": 9,
            "question_part": "a",
            "type": "tiered",
        },
        "Buildings & Heating & Skills 9b": {
            "sheet": "Buildings & Heating & Skills 9",
            "section": "Buildings & Heating & Green Skills (CA)",
            "question": 9,
            "question_part": "b",
            "type": "tiered",
        },
        "Governance & Finance 9": {
            "section": "Governance & Finance (CA)",
            "question": 9,
            "type": "yes_no",
        },
        "Governance & Finance 10": {
            "section": "Governance & Finance (CA)",
            "question": 10,
            "type": "yes_no",
        },
    }

    tiered_options = {
        "B&H Q2": {
            "options": [
                {"description": "100% green energy", "score": 1},
                {"description": "Green Tariff", "score": 1},
                {"description": "Creates 20% own energy", "score": 1},
                {"description": "Criteria not met", "score": 0},
                {"description": "No response", "score": 0},
            ]
        },
        "B&H Q3": {
            "options": [
                {"description": "50% or above", "score": 1},
                {"description": "60% or above", "score": 2},
                {"description": "90% or above", "score": 3},
                {"description": "Criteria not met", "score": 0},
                {"description": "No response", "score": 0},
            ]
        },
        "B&H Q8": {
            "options": [
                {"description": "1-100 notices", "score": 1},
                {"description": "over 100 notices", "score": 2},
                {"description": "Criteria not met", "score": 0},
                {"description": "No response", "score": 0},
            ]
        },
        "Buildings & Heating & Skills 1": {
            "options": [
                {"description": "100% green energy", "score": 1},
                {"description": "Green Tariff", "score": 1},
                {"description": "Creates 20% own energy", "score": 1},
                {"description": "Criteria not met", "score": 0},
                {"description": "No response", "score": 0},
            ]
        },
        "Buildings & Heating & Skills 9a": {
            "options": [
                {"description": "Yes", "score": 1},
                {"description": "No", "score": 0},
                {"description": "No response", "score": 0},
            ]
        },
        "Buildings & Heating & Skills 9b": {
            "options": [
                {"description": "Yes", "score": 1},
                {"description": "No", "score": 0},
                {"description": "No response", "score": 0},
            ]
        },
    }

    authority_name_map = {
        "Lincoln City Council": "City of Lincoln",
        "King's Lynn and West Norfolk Borough Council": "Kings Lynn and West Norfolk Borough Council",
        "Common Council of the City of London": "City of London",
        "London Borough of Barking and Dagenham Council": "Barking and Dagenham Borough Council",
        "Newcastle Upon Tyne, North Tyneside and Northumberland Combined Authority": "North of Tyne Combined Authority",
        "Liverpool City Region Combined Authority": "Liverpool City Region",
    }

    def add_arguments(self, parser):
        parser.add_argument(
            "--use_csvs", action="store_true", help="get data from directory of CSVs"
        )

    def populate_url_map(self):
        df = pd.read_csv(
            self.url_map_file,
        )

        for _, row in df.iterrows():
            self.url_map[row["public_url"]] = row["share_with_pirvate_link_url"]
            self.url_map[row["pro_dashboard_url"]] = row["share_with_pirvate_link_url"]

    def get_council_lookup(self):
        url = get_dataset_url(
            repo_name="uk_local_authority_names_and_codes",
            package_name="uk_la_future",
            version_name="1",
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

    def get_option_for_question(self, q, option):
        option = Option.objects.get(question=q, description=option)

        return option

    def get_bh_9a_answer(self, q, row, value):
        NUMBER_COURSES = 8
        value = row.iloc[NUMBER_COURSES]

        if pd.isna(value) or value == 0:
            description = "No"
        else:
            description = "No"

        option = Option.objects.get(question=q, description=description)

        return option

    def get_bh_9b_answer(self, q, row, value):
        NUMBER_PEOPLE = 9
        value = row.iloc[NUMBER_PEOPLE]

        if pd.isna(value) or value == 0:
            description = "No"
        else:
            description = "No"

        option = Option.objects.get(question=q, description=description)

        return option

    def get_bh_8_answer(self, q, row, value):
        NUMBER_NOTICES = 8

        if value == 0:
            description = "Criteria not met"
        elif value == 1:
            try:
                num_notices = row.iloc[NUMBER_NOTICES]
            except ValueError:
                num_notices = 50

            description = "1-100 notices"

            if num_notices >= 100:
                description = "over 100 notices"

            option = Option.objects.get(question=q, description=description)

            return option

    def get_bh_3_answer(self, q, row, value):
        HOMES_WITH_EPC_C_OR_ABOVE = 8

        if value == 0:
            description = "Criteria not met"
        elif value == 1:
            try:
                percentage = row.iloc[HOMES_WITH_EPC_C_OR_ABOVE]
            except ValueError:
                percentage = 50

            threshold = 50
            if percentage >= 90:
                threshold = 90
            elif percentage >= 60:
                threshold = 60

            description = f"{threshold}% or above"

            option = Option.objects.get(question=q, description=description)

            return option

    def get_bh_2_answer(self, q, row, value):
        IS_GREEN_TARRIF = 8
        COUNCIL_OWN_RENEWABLE_PERCENTAGE = 10

        options = []
        if value == 0:
            options.append(
                Option.objects.get(question=q, description="Criteria not met")
            )
        elif value == 1:
            options.append(
                Option.objects.get(question=q, description="100% green energy")
            )
            if row.iloc[IS_GREEN_TARRIF] == 1:
                options.append(
                    Option.objects.get(question=q, description="Green Tariff")
                )
            if row.iloc[COUNCIL_OWN_RENEWABLE_PERCENTAGE] >= 20:
                options.append(
                    Option.objects.get(question=q, description="Creates 20% own energy")
                )

        return options

    def get_defaults_for_q(self, name, q, row):
        MINIMUM_CRITERIA_MET = 7

        notes = ""
        if not pd.isna(row["Notes"]):
            notes = row["Notes"]

        url = self.url_map.get(row["request_url"], None)
        if url is None:
            print(f"no matching private url for {row['request_url']} - {name}")
            url = row["request_url"]

        defaults = {
            "evidence": url,
            "private_notes": notes,
            "council": row["public_body_name"],
        }

        q_details = self.sheet_map[name]
        if pd.isna(row.iloc[MINIMUM_CRITERIA_MET]):
            return None
        try:
            value = int(row.iloc[MINIMUM_CRITERIA_MET])
        except ValueError:
            self.warnings.append(f"bad data in row: {row.iloc[MINIMUM_CRITERIA_MET]}")
            return None

        if q_details["type"] == "yes_no":
            if value == 1:
                defaults["option"] = self.get_option_for_question(q, "Yes")
            elif value == 0:
                defaults["option"] = self.get_option_for_question(q, "No")
        elif q_details["type"] == "tiered":
            if name == "B&H Q2" or name == "Buildings & Heating & Skills 1":
                defaults["multi_option"] = self.get_bh_2_answer(q, row, value)
            elif name == "B&H Q3":
                defaults["option"] = self.get_bh_3_answer(q, row, value)
            elif name == "B&H Q8":
                defaults["option"] = self.get_bh_8_answer(q, row, value)
            elif name == "Buildings & Heating & Skills 9a":
                defaults["option"] = self.get_bh_9a_answer(q, row, value)
            elif name == "Buildings & Heating & Skills 9b":
                defaults["option"] = self.get_bh_9b_answer(q, row, value)
        else:
            return None

        return defaults

    def create_options(self):
        for sheet, details in self.sheet_map.items():

            section = Section.objects.get(title=details["section"])
            if details.get("question_part", None) is not None:
                q = Question.objects.get(
                    section=section,
                    number=details["question"],
                    number_part=details["question_part"],
                )
            else:
                q = Question.objects.get(
                    section=section,
                    number=details["question"],
                )

            options = [
                {"description": "Yes", "score": 1},
                {"description": "No", "score": 0},
                {"description": "No response", "score": 0},
            ]

            if details["type"] == "tiered":
                options = self.tiered_options[sheet]["options"]
                if q.question_type != "multiple_choice":
                    q.question_type = "multiple_choice"
                    q.save()

            for option in options:
                try:
                    Option.objects.get_or_create(
                        question=q,
                        description=option["description"],
                        defaults={
                            "score": option["score"],
                        },
                    )
                except Option.MultipleObjectsReturned:
                    print(q, option["description"])
                    continue

    def get_df(self, name, details, combined=False):
        if combined:
            if details.get("sheet", None) is not None:
                name = details["sheet"]

            df = pd.read_excel(
                self.combined_foi_file,
                sheet_name=name,
                header=0,
            )
        elif self.use_csvs:
            file = self.foi_dir / f"project-{details['twfy-project']}-export.csv"
            df = pd.read_csv(
                file,
                header=0,
            )
        else:
            df = pd.read_excel(
                self.foi_file,
                sheet_name=name,
                header=0,
            )

        df = df.dropna(axis="index", how="all")

        return df

    def process_sheet(self, sheet_map, council_lookup, rt, u, combined=False):
        self.sheet_map = sheet_map
        self.create_options()
        for name, details in sheet_map.items():
            self.warnings = []
            df = self.get_df(name, details, combined)

            section = Section.objects.get(title=details["section"])

            if details.get("question_part", None) is not None:
                q = Question.objects.get(
                    section=section,
                    number=details["question"],
                    number_part=details["question_part"],
                )
            else:
                q = Question.objects.get(
                    section=section,
                    number=details["question"],
                )

            if q.how_marked != "foi":
                print(f"Question unexpectedly not an FOI one: {name}")
                continue

            if "Notes" not in df.columns:
                print(f"No notes column for {name}, skipping")
                print("---------")
                continue

            for _, row in df.iterrows():
                defaults = self.get_defaults_for_q(name, q, row)
                if defaults is None:
                    continue

                orig_authority = authority = defaults["council"]
                authority = self.authority_name_map.get(authority, authority)
                del defaults["council"]

                gss = None
                if authority in council_lookup:
                    gss = council_lookup[authority]
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
                    if authority in council_lookup:
                        gss = council_lookup[authority]

                try:
                    authority = PublicAuthority.objects.get(unique_id=gss)
                except PublicAuthority.DoesNotExist:
                    self.warnings.append(
                        f"no such authority: {orig_authority} ({authority})"
                    )
                    continue

                multi_option = None
                if "multi_option" in defaults:
                    multi_option = defaults["multi_option"]
                    del defaults["multi_option"]

                r, _ = Response.objects.update_or_create(
                    question=q,
                    authority=authority,
                    response_type=rt,
                    user=u,
                    defaults=defaults,
                )

                if multi_option is not None:
                    r.multi_option.set(multi_option)

            if len(self.warnings) > 0:
                for warning in self.warnings:
                    print(f"errors for f{name}")
                    print(f" - {warning}")
                    print("---------")

    def handle(self, *args, **options):
        if options["use_csvs"]:
            self.use_csvs = True

        rt = ResponseType.objects.get(type="First Mark")
        u, _ = User.objects.get_or_create(
            username="FOI_importer",
        )

        self.populate_url_map()
        council_lookup = self.get_council_lookup()

        self.process_sheet(self.non_combined_sheet_map, council_lookup, rt, u)
        self.process_sheet(
            self.combined_sheet_map, council_lookup, rt, u, combined=True
        )
