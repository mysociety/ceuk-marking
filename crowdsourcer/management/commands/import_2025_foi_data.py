import re
from collections import defaultdict

from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

import pandas as pd
from mysoc_dataset import get_dataset_url

from crowdsourcer.models import (
    MarkingSession,
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

    foi_file = settings.BASE_DIR / "data" / "scorecards-2025" / "fois.xlsx"
    foi_dir = settings.BASE_DIR / "data" / "foi_csvs"
    url_map_file = (
        settings.BASE_DIR / "data" / "scorecards-2025" / "foi-private-link-url.csv"
    )
    new_url_map_file = (
        settings.BASE_DIR
        / "data"
        / "scorecards-2025"
        / "updated-foi-private-link-url.csv"
    )

    combined_foi_file = settings.BASE_DIR / "data" / "combined_foi_data.xlsx"

    warnings = []
    url_map = {}

    sheet_section_map = {
        "Buildings": "B&H",
        "Gov&Finance": "G&F",
        "Collab": "C&E",
    }

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
            "include_notes_col_names": True,
            "notes": [
                "If yes, fill in the statistics provided. What % of homes have received an EPC rating of C or above?"
            ],
        },
        "B&H Q6": {
            "section": "Buildings & Heating",
            "question": 6,
            "type": "yes_no",
            "twfy-project": 18,
            "include_notes_col_names": True,
            "notes": ["Please list roles that work in this area"],
        },
        "B&H Q8": {
            "section": "Buildings & Heating",
            "question": 8,
            "type": "tiered",
            "twfy-project": 17,
            "include_notes_col_names": True,
            "notes": [
                "How many MEES investigations: [number]",
                "How many Enforcement notices: [number]",
                "How many Enforcement Actions: [number]",
            ],
        },
        "C&E Q3": {
            "section": "Collaboration & Engagement",
            "question": 3,
            "type": "yes_no",
            "twfy-project": 16,
            "include_notes_col_names": True,
            "notes": [
                "Evidence provided for type of lobbying (letter/email/meeting/none provided:",
                "Target of lobbying (UK national government, Welsh Government, Scottish Government, Northern Ireland Executive):",
                "Council ask of government (government action/further council funding or support):",
            ],
        },
        "C&E Q12": {
            "section": "Collaboration & Engagement",
            "question": 12,
            "type": "yes_no",
            "include_notes_col_names": True,
            "notes": [
                "Does the agreement between the council and employee representative body (including recognised trade union) making explicit reference to contributing to climate change related work?",
                "Were employee representatives bodies consulted during the development of the Climate Action Plan AND there are plans in place to continue engaging employee representative bodies in matters relating to the implementation of the Climate Action Plan?",
                "Evidence provided (policy/agreement/consultation evidence/none provided)",
            ],
        },
        "G&F Q8": {
            "section": "Governance & Finance",
            "question": 8,
            "type": "multi",
            "twfy-project": 14,
            "include_notes_col_names": True,
            "notes": [
                "Please copy and paste the list of roles:",
            ],
        },
        "G&F Q9": {
            "section": "Governance & Finance",
            "question": 9,
            "type": "multi",
            "include_notes_col_names": True,
            "notes": [
                "Notes (please add in how many senior management have been trained if any)",
                "Notes (please add in how many councillors have been trained if any and state if they are leadership or not)",
                "If provided, please list the type of training:",
            ],
            "twfy-project": 11,
        },
    }

    q11_map = {
        "roads": {
            "section": "Transport",
            "question": 11,
            "type": "yes_no",
            "sheet": "Transport.Q11.Roads",
        },
        "airports": {
            "section": "Transport",
            "question": 11,
            "type": "Multiple",
            "sheet": "Transport.Q11.Airports",
        },
    }

    combined_sheet_map = {
        "C&E Q3": {
            "section": "Collaboration & Engagement (CA)",
            "question": 3,
            "question_part": "a",
            "type": "yes_no",
            "include_notes_col_names": True,
            "notes": [
                "Evidence provided for type of lobbying (letter/email/meeting/none provided:",
                "Target of lobbying (UK national government, Welsh Government, Scottish Government, Northern Ireland Executive):",
                "Council ask of government (government action/further council funding or support):",
            ],
        },
        "C&E Q12": {
            "section": "Collaboration & Engagement (CA)",
            "question": 10,
            "type": "yes_no",
            "include_notes_col_names": True,
            "notes": [
                "Does the agreement between the council and employee representative body (including recognised trade union) making explicit reference to contributing to climate change related work?",
                "Were employee representatives bodies consulted during the development of the Climate Action Plan AND there are plans in place to continue engaging employee representative bodies in matters relating to the implementation of the Climate Action Plan?",
                "Evidence provided (policy/agreement/consultation evidence/none provided)",
            ],
        },
        "B&H Q2": {
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
        "G&F Q8": {
            "section": "Governance & Finance (CA)",
            "question": 9,
            "type": "multi",
            "include_notes_col_names": True,
            "notes": [
                "Please copy and paste the list of roles:",
            ],
        },
        "G&F Q9": {
            "section": "Governance & Finance (CA)",
            "question": 10,
            "type": "yes_no",
            "include_notes_col_names": True,
            "notes": [
                "Notes (please add in how many senior management have been trained if any)",
                "Notes (please add in how many councillors have been trained if any and state if they are leadership or not)",
                "If provided, please list the type of training:",
            ],
        },
        "Transport Q4c": {
            "section": "Transport (CA)",
            "question": 4,
            "question_part": "c",
            "type": "multi",
            "include_notes_col_names": True,
            "notes": ["Percentage of the bus fleet that is zero emission? [number]"],
        },
    }

    authority_name_map = {
        "Lincoln City Council": "City of Lincoln",
        "King's Lynn and West Norfolk Borough Council": "Kings Lynn and West Norfolk Borough Council",
        "Common Council of the City of London": "City of London",
        "London Borough of Barking and Dagenham Council": "Barking and Dagenham Borough Council",
        "Newcastle Upon Tyne, North Tyneside and Northumberland Combined Authority": "North of Tyne Combined Authority",
        "Liverpool City Region Combined Authority": "Liverpool City Region",
        "St Helens Metropolitan Borough Council": "St. Helens Borough Council",
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
            self.url_map[row["request_url"]] = row["request_private_link"]
            self.url_map[row["project_url"]] = row["request_private_link"]

        df = pd.read_csv(
            self.new_url_map_file,
        )

        for _, row in df.iterrows():
            self.url_map[row["request_url"].strip()] = row[
                "request_private_link"
            ].strip()

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

    def get_option_for_question(self, q, option):
        try:
            option = Option.objects.get(question=q, description=option)
        except Option.DoesNotExist:
            fail = True
            if option == "Evidence does not meet criteria":
                option = "Evidence doesn't meet criteria"
                try:
                    option = Option.objects.get(question=q, description=option)
                    fail = False
                except Option.DoesNotExist:
                    pass

            if fail:
                self.stderr.write(f"No option “{option}‟ found for {q}")
                assert False

        return option

    def get_bh_9a_answer(self, q, row, value):
        NUMBER_COURSES = 8
        value = row.iloc[NUMBER_COURSES]

        if pd.isna(value) or value == 0 or value == "No":
            description = "No"
        else:
            description = "No"

        option = Option.objects.get(question=q, description=description)

        return option

    def get_bh_9b_answer(self, q, row, value):
        NUMBER_PEOPLE = 9
        value = row.iloc[NUMBER_PEOPLE]

        if pd.isna(value) or value == 0 or value == "No":
            description = "No"
        else:
            description = "No"

        option = Option.objects.get(question=q, description=description)

        return option

    def get_bh_8_answer(self, q, row, value):
        counts = {}
        count_map = {
            "investigations": "How many MEES investigations: [number]",
            "notices": "How many Enforcement notices: [number]",
            "actions": "How many Enforcement Actions: [number]",
        }
        for count, col in count_map.items():
            val = 0
            if not pd.isna(row[col]):
                try:
                    val = int(row[col])
                except ValueError:
                    self.stderr.write(
                        f"Failed to convert “{col}” to int for {row['public_body']}: {row[col]}"
                    )
                    val = 0
            counts[count] = val

        description = "Evidence doesn't meet criteria"

        if counts["investigations"] > 0:
            description = "one or more investigations"

        if counts["notices"] > 0 or counts["actions"] > 0:
            description = "one or more compliance or enforcement"

        option = Option.objects.get(question=q, description=description)

        return option

    def get_bh_3_answer(self, q, row, value):
        if value == 0 or value == "No":
            description = "Council directly owns or manages less than 100 homes so question doesn't apply"
        elif value == 1 or value == "Yes":
            try:
                percentage = row[
                    "If yes, fill in the statistics provided. What % of homes have received an EPC rating of C or above?"
                ]
            except ValueError:
                percentage = 50

            threshold = 0
            if percentage >= 90:
                threshold = 90
            elif percentage >= 60:
                threshold = 60
            elif percentage >= 50:
                threshold = 50

            if threshold > 0:
                description = f"Yes, {threshold}% or more"
            else:
                description = "Evidence doesn't meet criteria"

        option = Option.objects.get(question=q, description=description)

        return option

    def get_bh_2_answer(self, q, row, value):
        green_energy = False
        green_tariff = False
        greater_than_20 = False

        if row["Does the council have a green electricity tariff?"] == "Yes":
            green_energy = True

        if (
            row[
                "What % of the council's energy use is powered by local renewable electricity sources or their own renewable electricity sources? If none, please select 0%"
            ]
            >= 20
        ):
            greater_than_20 = True

        if (
            row[
                "Is that tariff with Green Energy UK plc, Good Energy Limited or Ecotricity?"
            ]
            == "Yes"
        ):
            green_tariff = True

        options = []
        if not green_energy and not green_tariff and not greater_than_20:
            options.append(
                Option.objects.get(
                    question=q, description="Evidence doesn't meet criteria"
                )
            )
        elif green_tariff or greater_than_20:
            options.append(
                Option.objects.get(
                    question=q,
                    description="Yes, 100% Green tariff with one of those 3 companies or generates 20% or more of its own energy through other renewable energy production",
                )
            )
        else:
            options.append(
                Option.objects.get(
                    question=q,
                    description="Yes, 100% Green tariff or generates 20% or more of its own energy from waste",
                )
            )

        return options

    def get_gf_8_answer(self, q, row, value):
        if value == 0 or value == "No" or pd.isna(value):
            description = "No response from FOI"
        else:
            try:
                total_staff = row["How many staff does the council directly employ?"]
                sixty_percent_staff = row[
                    "How many staff spend 60% (0.6) or more of their time implementing the climate action plan/policies?"
                ]
                percent_staff = sixty_percent_staff / total_staff
            except ValueError:
                percent_staff = 0

            description = "Evidence doesn't meet criteria"

            if percent_staff >= 0.02:
                description = "Equal to or more than 2%"
            elif percent_staff >= 0.01:
                description = "Equal to or more than 1%"
            elif percent_staff >= 0.005:
                description = "Equal to or more than 0.5%"

        option = Option.objects.get(question=q, description=description)

        return option

    def get_gf_9_answer(self, q, row, value):
        senior_training = (
            row[
                "Have all senior management received carbon literacy training since 1st January 2015?"
            ]
            == "Yes"
        )
        councillor_training = (
            row[
                "Have all councillors in leadership positions received carbon literacy training since 1st January 2015?"
            ]
            == "Yes"
        )

        if senior_training and councillor_training:
            description = "Yes"
        elif senior_training:
            description = "Not all councillors in the cabinet or committee chairs trained (evidence doesn't meet criteria)"
        elif councillor_training:
            description = (
                "Not all senior staff trained (evidence doesn't meet criteria)"
            )
        else:
            description = "Evidence doesn't meet criteria "

        option = Option.objects.get(question=q, description=description)

        return option

    def get_tran_ca_4c(self, q, row, value):
        value = row["Percentage of the bus fleet that is zero emission? [number]"]

        if pd.isna(value):
            description = "Evidence doesn't meet criteria"
        elif value >= 50:
            description = "50% or over"
        elif value >= 25:
            description = "25% or over"
        elif value >= 10:
            description = "10% or over"
        else:
            description = "Evidence doesn't meet criteria"

        option = Option.objects.get(question=q, description=description)

        return option

    def get_standard_defaults(self, name, row):
        notes = ""
        if row.get("Notes") and not pd.isna(row["Notes"]):
            notes = str(row["Notes"])

        url = self.url_map.get(row["request_url"], None)
        if url is None:
            print(f"no matching private url for {row['request_url']} - {name}")
            url = row["request_url"]

        defaults = {
            "evidence": url,
            "private_notes": notes,
            "council": row["public_body"],
        }

        return defaults

    def get_defaults_for_q(self, name, q, row, details):
        MINIMUM_CRITERIA_MET = 11

        defaults = self.get_standard_defaults(name, row)

        if details.get("notes"):
            notes = []
            if defaults["private_notes"].strip() != "":
                notes.append(defaults["private_notes"].strip())
            for col in details["notes"]:
                if not pd.isna(row[col]):
                    s = str(row[col]).strip()
                    if s != "":
                        if details.get("include_notes_col_names"):
                            notes.append(f"\n{col}")
                        else:
                            notes.append("\n")
                        notes.append(s)
            defaults["private_notes"] = "\n".join(notes)

        q_details = self.sheet_map[name]
        if pd.isna(row.iloc[MINIMUM_CRITERIA_MET]):
            value = 0
        else:
            try:
                value = row.iloc[MINIMUM_CRITERIA_MET]
            except ValueError:
                self.warnings.append(
                    f"bad data in row: {row.iloc[MINIMUM_CRITERIA_MET]}"
                )
                return None

        option_name = "option"
        if q_details["type"] == "tiered":
            option_name = "multi_option"

        if row["classification"].strip() in ["Awaiting response", "Refused"]:
            defaults[option_name] = self.get_option_for_question(
                q, "No response from FOI"
            )
        elif row["classification"] == "Data not held":
            defaults[option_name] = self.get_option_for_question(
                q, "Evidence doesn't meet criteria"
            )
        elif q_details["type"] == "yes_no":
            if value == 1 or value == "Yes":
                defaults["option"] = self.get_option_for_question(q, "Yes")
            elif value == 0 or value == "No":
                defaults["option"] = self.get_option_for_question(
                    q, "Evidence does not meet criteria"
                )
        elif q_details["type"] == "multi":
            if name == "G&F Q8":
                defaults["option"] = self.get_gf_8_answer(q, row, value)
            elif name == "G&F Q9":
                defaults["option"] = self.get_gf_9_answer(q, row, value)
            elif name == "Transport Q4c":
                defaults["option"] = self.get_tran_ca_4c(q, row, value)
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

    def get_sheets(self, combined=False):
        if combined:
            ex = pd.ExcelFile(self.combined_foi_file)
        else:
            ex = pd.ExcelFile(self.foi_file)

        sheets = {}
        for sheet in ex.sheet_names:
            m = re.match(r"([\w&]+)\.(Q\d+)", sheet)
            if m:
                map_name = self.sheet_section_map.get(m.group(1), m.group(1))
                sheets[sheet] = f"{map_name} {m.group(2)}"

        sheets["CA.Transport.ZeroEmissionBuses "] = "Transport Q4c"
        return sheets

    def get_df(self, name):
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

    def process_sheet(self, sheet_map, council_lookup, rt, u, ms, combined=False):
        sheets = self.get_sheets(combined)
        self.sheet_map = sheet_map
        for sheet, name in sheets.items():
            details = sheet_map.get(name)
            if details is None:
                continue

            if details.get("skip"):
                print(f"skipping {details['section']} {details['question']} for now")
                continue

            print(f"{details['section']} {details['question']}")

            self.warnings = []
            df = self.get_df(sheet)

            section = Section.objects.get(title=details["section"], marking_session=ms)

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

            # if q.how_marked != "foi":
            # print(f"Question unexpectedly not an FOI one: {name}")
            # continue

            if "Notes" not in df.columns and not details.get("notes"):
                print(f"No notes column for {name}, skipping")
                print("---------")
                continue

            for _, row in df.iterrows():
                defaults = self.get_defaults_for_q(name, q, row, details)
                if defaults is None:
                    print(f"No defaults for {name} - {row['public_body']}")
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
                else:
                    r.multi_option.clear()

            if len(self.warnings) > 0:
                for warning in self.warnings:
                    print(f"errors for {name}")
                    print(f" - {warning}")
                    print("---------")

    def process_q11(self, council_lookup, rt, u, ms):
        self.warnings = []
        MINIMUM_CRITERIA_MET = 11
        NOTES = 15
        answers = defaultdict(dict)

        q = Question.objects.get(
            section__title="Transport", section__marking_session=ms, number=11
        )

        print("Transport Q11")

        for foi in ["roads", "airports"]:
            sheet = self.q11_map[foi]["sheet"]
            df = pd.read_excel(
                self.foi_file,
                sheet_name=sheet,
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
                    value = "No"
                else:
                    value = row.iloc[MINIMUM_CRITERIA_MET]

                all_defaults = answers[authority.name]
                if not all_defaults:
                    all_defaults["private_notes"] = defaults["private_notes"]
                else:
                    all_defaults["private_notes"] = (
                        all_defaults["private_notes"]
                        + "\n\n"
                        + defaults["private_notes"]
                    )

                if foi == "airports" and not pd.isna(
                    row[
                        "If possible, please copy and paste the list of accepted new or expanded airport planning proposals:"
                    ]
                ):
                    all_defaults["private_notes"] = (
                        all_defaults["private_notes"]
                        + "\nlist of accepted new or expanded proposals:\n"
                        + str(
                            row[
                                "If possible, please copy and paste the list of accepted new or expanded airport planning proposals:"
                            ]
                        )
                    )
                if foi == "roads" and not pd.isna(
                    row[
                        "If possible, please copy and paste the list of accepted new or expanded roads:"
                    ]
                ):
                    all_defaults["private_notes"] = (
                        all_defaults["private_notes"]
                        + "\nlist of accepted new or expanded roads:\n"
                        + str(
                            row[
                                "If possible, please copy and paste the list of accepted new or expanded roads:"
                            ]
                        )
                    )

                if all_defaults.get("evidence"):
                    all_defaults["evidence"] = (
                        all_defaults["evidence"] + "\n" + defaults["evidence"]
                    )
                else:
                    all_defaults["evidence"] = defaults["evidence"]

                del defaults["evidence"]
                del defaults["private_notes"]

                defaults[foi] = value
                all_defaults = {**all_defaults, **defaults}
                all_defaults["authority"] = authority
                answers[authority.name] = all_defaults

        for authority, defaults in answers.items():
            multi_option = []
            defaults["option"] = None
            if defaults.get("roads", None) is not None:
                if defaults["roads"] == "Yes":
                    multi_option.append(
                        Option.objects.get(question=q, description="Approved Roads")
                    )
                del defaults["roads"]
            if defaults.get("airports", None) is not None:
                if defaults["airports"] == "Yes":
                    multi_option.append(
                        Option.objects.get(question=q, description="Approved Airports")
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

    def process_ca_q9(self, council_lookup, rt, u, ms):
        sheet = "CA.B&H.GreenSkillsCourses (9a a"

        df = pd.read_excel(
            self.foi_file,
            sheet_name=sheet,
            header=0,
        )
        df = df.dropna(axis="index", how="all")

        q9a = Question.objects.get(
            section__title="Buildings & Heating & Green Skills (CA)",
            section__marking_session=ms,
            number=9,
            number_part="a",
        )
        q9b = Question.objects.get(
            section__title="Buildings & Heating & Green Skills (CA)",
            section__marking_session=ms,
            number=9,
            number_part="b",
        )

        print("Buildings & Heating & Green Skills (CA) Q9a&b")

        for _, row in df.iterrows():
            how_many_trained = row[
                "How many people have been trained on green skills/green jobs courses between 1st Sept 2020 and 1st Sept 2023?"
            ]
            courses = row["Total"]

            if pd.isna(how_many_trained):
                how_many_trained = 0

            try:
                how_many_trained = int(how_many_trained)
            except ValueError:
                self.stderr.write(
                    f"Could not convert how_many_trained to int: {how_many_trained}, {row['public_body']}"
                )
                continue

            if row["classification"] in ["Awaiting response", "Refused"]:
                q9b_option = self.get_option_for_question(q9b, "No response from FOI")
                q9a_option = self.get_option_for_question(q9a, "No response from FOI")
            elif row["classification"] == "Data not held":
                q9b_option = self.get_option_for_question(
                    q9b, "Evidence doesn't meet criteria"
                )
                q9a_option = self.get_option_for_question(
                    q9a, "Evidence doesn't meet criteria"
                )
            else:
                if how_many_trained > 1000:
                    q9b_option = Option.objects.get(question=q9b, description="Yes")
                else:
                    q9b_option = Option.objects.get(
                        question=q9b, description="Evidence doesn't meet criteria"
                    )

                defaults_9b = self.get_standard_defaults(
                    "Buildings & Heating & Skills 9b", row
                )
                if not pd.isna(row["Notes"]):
                    defaults_9b["private_notes"] = row["Notes"]

                authority = defaults_9b["council"]
                del defaults_9b["council"]

                authority = self.get_authority(authority, council_lookup)
                if authority is None:
                    continue

                if courses >= 60:
                    q9a_option = self.get_option_for_question(q9a, "Yes")
                else:
                    q9a_option = self.get_option_for_question(
                        q9a, "Evidence doesn't meet criteria"
                    )

                defaults_9a = self.get_standard_defaults(
                    "Buildings & Heating & Skills 9a", row
                )
                if not pd.isna(row["Notes"]):
                    defaults_9a["private_notes"] = row["Notes"]

                if not pd.isna(row.iloc[13]):
                    defaults_9a["private_notes"] = (
                        defaults_9a["private_notes"]
                        + "\nnumber of courses:\n"
                        + str(courses)
                        + "\n"
                        + "\nlist of courses:\n"
                        + str(row.iloc[13])
                        + "\n"
                    )

                del defaults_9a["council"]

            defaults_9b["option"] = q9b_option
            defaults_9a["option"] = q9a_option

            r, _ = Response.objects.update_or_create(
                question=q9b,
                authority=authority,
                response_type=rt,
                user=u,
                defaults=defaults_9b,
            )

            r, _ = Response.objects.update_or_create(
                question=q9a,
                authority=authority,
                response_type=rt,
                user=u,
                defaults=defaults_9a,
            )

    def handle(self, *args, **options):
        if options["use_csvs"]:
            self.use_csvs = True

        rt = ResponseType.objects.get(type="First Mark")
        ms = MarkingSession.objects.get(label="Scorecards 2025")
        u, _ = User.objects.get_or_create(
            username="FOI_importer",
        )

        # ex = pd.ExcelFile(self.foi_file)
        # print(ex.sheet_names)

        self.populate_url_map()
        council_lookup = self.get_council_lookup()
        self.process_sheet(self.non_combined_sheet_map, council_lookup, rt, u, ms)
        self.process_sheet(self.combined_sheet_map, council_lookup, rt, u, ms)
        self.process_q11(council_lookup, rt, u, ms)
        self.process_ca_q9(council_lookup, rt, u, ms)
