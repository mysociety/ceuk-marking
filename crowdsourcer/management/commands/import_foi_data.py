from collections import defaultdict

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
            "section": "Collaboration & Engagement",
            "question": 3,
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
    }

    q11_map = {
        "roads": {
            "section": "Transport",
            "question": 11,
            "type": "yes_no",
            "twfy-project": 15,
        },
        "airports": {
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
        "Transport 11": {
            "options": [
                {"description": "Approved roads", "score": 1},
                {"description": "Approved airport", "score": 1},
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

        parser.add_argument(
            "--transport_q11_only",
            action="store_true",
            help="only import transport q11",
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

        if value == 0 or pd.isna(value):
            description = "Criteria not met"
        else:
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

    def get_standard_defaults(self, name, row):
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

        return defaults

    def get_defaults_for_q(self, name, q, row):
        MINIMUM_CRITERIA_MET = 7

        defaults = self.get_standard_defaults(name, row)

        q_details = self.sheet_map[name]
        if pd.isna(row.iloc[MINIMUM_CRITERIA_MET]):
            value = 0
        else:
            try:
                value = int(row.iloc[MINIMUM_CRITERIA_MET])
            except ValueError:
                self.warnings.append(
                    f"bad data in row: {row.iloc[MINIMUM_CRITERIA_MET]}"
                )
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
                defaults["multi_option"] = self.get_bh_3_answer(q, row, value)
            elif name == "B&H Q8":
                defaults["multi_option"] = self.get_bh_8_answer(q, row, value)
            elif name == "Buildings & Heating & Skills 9a":
                defaults["multi_option"] = self.get_bh_9a_answer(q, row, value)
            elif name == "Buildings & Heating & Skills 9b":
                defaults["multi_option"] = self.get_bh_9b_answer(q, row, value)
        else:
            return None

        return defaults

    def write_options_to_db(self, q, options):
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

            self.write_options_to_db(q, options)

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

    def get_authority(self, authority, council_lookup):
        orig_authority = authority
        authority = self.authority_name_map.get(authority, authority)

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
            self.warnings.append(f"no such authority: {orig_authority} ({authority})")
            return None

        return authority

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
                    print(f"No defaults for {name} - {row['public_body_name']}")
                    continue

                authority = defaults["council"]
                del defaults["council"]

                authority = self.get_authority(authority, council_lookup)
                if authority is None:
                    continue

                multi_option = None
                if "multi_option" in defaults:
                    multi_option = defaults["multi_option"]
                    if isinstance(multi_option, Option):
                        multi_option = (multi_option,)
                    defaults["option"] = None
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

    def process_q11(self, council_lookup, rt, u):
        self.warnings = []
        MINIMUM_CRITERIA_MET = 7
        NOTES = 8
        answers = defaultdict(dict)

        q = Question.objects.get(section__title="Transport", number=11)
        q.question_type = "multiple_choice"
        q.save()

        self.write_options_to_db(q, self.tiered_options["Transport 11"]["options"])

        try:
            Option.objects.get(question=q, description="Yes").delete()
        except Option.DoesNotExist:
            pass  # already deleted

        for foi in ["roads", "airports"]:
            project = self.q11_map[foi]["twfy-project"]
            file = self.foi_dir / f"project-{project}-export.csv"
            df = pd.read_csv(
                file,
                header=0,
            )
            df = df.dropna(axis="index", how="all")
            for _, row in df.iterrows():
                defaults = self.get_standard_defaults(f"Transport 11 {foi}", row)
                if not pd.isna(row.iloc[NOTES]):
                    defaults["private_notes"] = row.iloc[NOTES]

                defaults["private_notes"] = f"{foi}\n{defaults['private_notes']}"
                defaults["evidence"] = f"{foi}: {defaults['evidence']}"

                authority = defaults["council"]
                del defaults["council"]

                authority = self.get_authority(authority, council_lookup)
                if authority is None:
                    continue

                if pd.isna(row.iloc[MINIMUM_CRITERIA_MET]):
                    value = 0
                else:
                    try:
                        value = int(row.iloc[MINIMUM_CRITERIA_MET])
                    except ValueError:
                        self.warnings.append(
                            f"bad data in row: {row.iloc[MINIMUM_CRITERIA_MET]}"
                        )
                        continue

                all_defaults = answers[authority.name]
                if all_defaults:
                    all_defaults["private_notes"] = (
                        all_defaults["private_notes"] + "\n" + defaults["private_notes"]
                    )
                    del defaults["private_notes"]
                    all_defaults["evidence"] = (
                        all_defaults["evidence"] + "\n" + defaults["evidence"]
                    )
                    del defaults["evidence"]

                defaults[foi] = value
                all_defaults = {**all_defaults, **defaults}
                all_defaults["authority"] = authority
                answers[authority.name] = all_defaults

        for authority, defaults in answers.items():
            multi_option = []
            defaults["option"] = None
            if defaults.get("roads", None) is not None:
                if defaults["roads"] == 1:
                    multi_option.append(
                        Option.objects.get(question=q, description="Approved roads")
                    )
                del defaults["roads"]
            if defaults.get("airports", None) is not None:
                if defaults["airports"] == 1:
                    multi_option.append(
                        Option.objects.get(question=q, description="Approved airport")
                    )
                del defaults["airports"]
            if len(multi_option) == 0:
                multi_option.append(Option.objects.get(question=q, description="No"))

            authority = defaults["authority"]
            del defaults["authority"]
            r, _ = Response.objects.update_or_create(
                question=q,
                authority=authority,
                response_type=rt,
                user=u,
                defaults=defaults,
            )

            r.multi_option.set(multi_option)

        if len(self.warnings) > 0:
            for warning in self.warnings:
                print("errors for Transport 11")
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

        if not options["transport_q11_only"]:
            self.process_sheet(self.non_combined_sheet_map, council_lookup, rt, u)
            self.process_sheet(
                self.combined_sheet_map, council_lookup, rt, u, combined=True
            )
        self.process_q11(council_lookup, rt, u)
