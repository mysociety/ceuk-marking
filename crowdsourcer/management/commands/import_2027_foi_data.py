import re
from collections import defaultdict
from typing import Optional

from django.conf import settings
from django.contrib.auth.models import User

import pandas as pd
from mysoc_dataset import get_dataset_url

from crowdsourcer.import_utils import BaseImporter
from crowdsourcer.models import (
    MarkingSession,
    Option,
    PublicAuthority,
    Question,
    Response,
    ResponseType,
    Section,
)


class Command(BaseImporter):
    help = "import FOI data"

    sheet_map = None
    use_csvs = False
    commit = False
    quiet = False

    foi_file = settings.BASE_DIR / "data" / "2027" / "fois.xlsx"
    url_map_file = settings.BASE_DIR / "data" / "2027" / "foi-private-link-url.csv"
    new_url_map_file = (
        settings.BASE_DIR / "data" / "2027" / "updated-foi-private-link-url.csv"
    )

    combined_foi_file = settings.BASE_DIR / "data" / "2027" / "combined_foi_data.xlsx"

    warnings = []
    url_map = {}

    answer_map_file = None
    answer_map = {}

    sheet_section_map = {}
    """
        "Buildings": "B&H",
        "Gov&Finance": "G&F",
        "Collab": "C&E",
    }
    """

    # get round limits on length of sheet names
    non_combined_sheet_map = {
        "Biodiversity.Q8.Planning Ecologist": {
            "section": "Biodiversity",
            "question": 8,
            "type": "yes_no",
            "answer_column": "Grace Answer",
            "notes_column": "Notes",
            "evidence": ["How many planning ecologists does the council have?"],
        },
        "Buildings.Q2.CouncilOpsRenewableEnergy": {
            "section": "Buildings & Heating",
            "question": 2,
            "type": "tiered",
            "evidence": [
                "What % of the council's energy use is powered by local renewable electricity sources or their own renewable electricity sources? If none, please state 0"
            ],
        },
        "Buildings.Q3.Council Homes (EnergyEfficiency)": {
            "section": "Buildings & Heating",
            "question": 3,
            "type": "tiered",
            "notes_column": "Notes",
            "header": 1,
            "evidence": [
                "How many homes does the council manage or own?",
                "If the council do own more than 100 homes and have provided a %, fill in the % given. What % of homes have received an EPC rating of C or above?",
                "If % not provided, Number of buildings with an A rating:",
                "If % not provided, Number of buildings with an B rating:",
                "If % not provided, Number of buildings with a C rating:",
                "If % not provided, Number of buildings with a D, E, F, G rating (combined):",
            ],
        },
        "Buildings.Q6.RetrofitStaff": {
            "section": "Buildings & Heating",
            "question": 6,
            "type": "yes_no",
            "evidence": [
                "Does the council have at least one retrofit staff member working for 3 or more days a week (0.6 FTE)?",
                "Evidence of criteria met",
            ],
        },
        "Buildings.Q8.MEES": {
            "section": "Buildings & Heating",
            "question": 8,
            "type": "tiered",
            "answer_column": "Grace answer",
            "header": 1,
            "evidence": [
                "How many MEES investigations: [number]",
                "How many Compliance notices: [number]",
                "How many Enforcement notices: [number]",
                "If provided as one single number, how many investigations, compliance or enforcement notices: [number]",
            ],
        },
        "Collab.Q3.Lobbying": {
            "section": "Collaboration & Engagement",
            "question": 3,
            "type": "multi",
            "notes_column": "Notes",
            "answer_column": "GRACE Answer",
            "evidence": [
                "Evidence provided for type of lobbying (letter/email/meeting/none provided:",
                "Target of lobbying (UK national government, Welsh Government, Scottish Government, Northern Ireland Executive):",
                "Authority ask of government (government action/further council funding or support):",
            ],
        },
        "Collab.Q12.EmployeeRep": {
            "section": "Collaboration & Engagement",
            "question": 12,
            "type": "yes_no",
            "notes_column": "Notes",
            "evidence": [
                "Is there a recognised trade union or employee forum representative sitting on the Climate Action Working Group (or equivalent)?",
                "Does the agreement between the council and the recognised trade union or the employee forum makes explicit reference to contributing to climate change related work?",
                "Were recognised trade unions or the employee forum consulted during the development of the Climate Action Plan AND there are plans in place to continue engaging them in matters relating to the implementation of the Climate Action Plan?",
            ],
        },
        "Gov&Finance.Q8.Climatestaff": {
            "section": "Governance & Finance",
            "question": 8,
            "type": "multi",
            "include_notes_col_names": True,
            "notes_column": "Notes",
            "evidence": [
                "How many staff does the council directly employ?",
                "How many staff spend 60% (0.6) or more of their time implementing the climate action plan/policies?",
                "Evidence of criteria met",
                "Additional Notes",
            ],
        },
        "Gov&Finance.Q9.ClimateTraining": {
            "section": "Governance & Finance",
            "question": 9,
            "type": "multi",
            "header": 1,
            "notes_column": "General notes",
            "evidence": [
                "Have all senior management received climate awareness, carbon literacy or equivalent training since 1st January 2015?",
                "Evidence (please add in how many senior management have been trained if any)",
                "Have all councillors in leadership positions received climate awareness, carbon literacy or equivalent since 1st January 2015 and before 7th May 2026?",
                "Evidence (please add in how many councillors have been trained if any and state if they are leadership or not)",
            ],
        },
        "skip": [
            "Transport.Q11.Roads",
            "Transport.Q11.Airports",
            "MA.Transport.ZeroEmissionBuses ",
            "MA.B&H.GreenSkillsCourses (9a a",
            "4 outstanding",
        ],
    }

    q11_map = {
        "roads": {
            "section": "Transport",
            "question": 11,
            "type": "multi",
            "sheet": "Transport.Q11.Roads",
            "notes_column": "Notes",
            "evidence": [
                "Has the council approved any new or expanded roads or road junctions since 1st January 2021?",
                "If possible, please copy and paste the list of accepted new or expanded roads:",
            ],
        },
        "airports": {
            "section": "Transport",
            "question": 11,
            "type": "multi",
            "sheet": "Transport.Q11.Airports",
            "notes_column": "Notes",
            "evidence": [
                "Has the council approved any new or expanded airport runways, terminals, measures to increase passenger numbers etc since 1st January 2020?",
                "If possible, please copy and paste the list of accepted new or expanded airport planning proposals:",
            ],
        },
    }

    combined_sheet_map = {
        "Collab.Q3.Lobbying": {
            "section": "Collaboration & Engagement (MA)",
            "question": 3,
            "question_part": "a",
            "type": "yes_no",
            "include_notes_col_names": True,
            "notes_column": "Notes",
            "answer_column": "GRACE Answer",
            "evidence": [
                "Evidence provided for type of lobbying (letter/email/meeting/none provided:",
                "Target of lobbying (UK national government, Welsh Government, Scottish Government, Northern Ireland Executive):",
                "Authority ask of government (government action/further council funding or support):",
            ],
        },
        "Collab.Q12.EmployeeRep": {
            "section": "Collaboration & Engagement (MA)",
            "question": 10,
            "type": "yes_no",
            "include_notes_col_names": True,
            "notes_column": "Notes",
            "evidence": [
                "Is there a recognised trade union or employee forum representative sitting on the Climate Action Working Group (or equivalent)?",
                "Does the agreement between the council and the recognised trade union or the employee forum makes explicit reference to contributing to climate change related work?",
                "Were recognised trade unions or the employee forum consulted during the development of the Climate Action Plan AND there are plans in place to continue engaging them in matters relating to the implementation of the Climate Action Plan?",
            ],
        },
        "Buildings.Q2.CouncilOpsRenewabl": {
            "section": "Buildings & Heating (MA)",
            "question": 1,
            "type": "tiered",
            "evidence": [
                "What % of the council's energy use is powered by local renewable electricity sources or their own renewable electricity sources? If none, please state 0"
            ],
        },
        "Gov&Finance.Q8.Climatestaff": {
            "section": "Governance & Finance (MA)",
            "question": 9,
            "type": "multi",
            "include_notes_col_names": True,
            "notes_column": "Notes",
            "evidence": [
                "How many staff does the council directly employ?",
                "How many staff spend 60% (0.6) or more of their time implementing the climate action plan/policies?",
                "Evidence of criteria met",
                "Additional Notes",
            ],
        },
        "Gov&Finance.Q9.ClimateTraining": {
            "section": "Governance & Finance (MA)",
            "question": 10,
            "type": "multi",
            "include_notes_col_names": True,
            "header": 1,
            "notes_column": "General notes",
            "evidence": [
                "Have all senior management received climate awareness, carbon literacy or equivalent training since 1st January 2015?",
                "Evidence (please add in how many senior management have been trained if any)",
                "Have all councillors in leadership positions received climate awareness, carbon literacy or equivalent since 1st January 2015 and before 7th May 2026?",
                "Evidence (please add in how many councillors have been trained if any and state if they are leadership or not)",
            ],
        },
        "MA.Transport.ZeroEmissionBuses ": {
            "section": "Transport (MA)",
            "question": 4,
            "question_part": "c",
            "type": "multi",
            "include_notes_col_names": True,
            "notes_column": "Notes",
            "evidence": [
                "Evidence: Percentage of the bus fleet that is zero emission? [number]"
            ],
        },
        "skip": [
            "Transport.Q11.Roads",
            "Transport.Q11.Airports",
            "Biodiversity.Q8.Planning Ecolog",
            "Buildings.Q3.Council Homes (Ene",
            "Buildings.Q6.RetrofitStaff",
            "Buildings.Q8.MEES",
            "MA.B&H.GreenSkillsCourses (9a a",
            "4 outstanding",
        ],
    }

    q9a_map = {
        "B&H (MA) Q9": {
            "section": "Buildings & Heating (MA)",
            "question": 9,
            "question_part": "a",
        }
    }

    q9b_map = {
        "B&H (MA) Q9": {
            "section": "Buildings & Heating (MA)",
            "question": 9,
            "question_part": "b",
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
        "Barnsley Metropolitan Borough Council": "Barnsley Borough Council",
        "Sheffield City Council": "Sheffield Council",
        "Hull and East Yorkshire Combined Authority": "Hull and East Yorkshire Mayoral Combined Authority",
        "York and North Yorkshire Combined Authority": "York and North Yorkshire Mayoral Combined Authority",
        "Transport for London": "Greater London Authority",
        "Transport for Greater Manchester": "Greater Manchester Combined Authority",
    }

    gss_map = {
        "E08000019": "E08000039",  # sheffield
        "E08000016": "E08000038",  # barnsley
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

        parser.add_argument(
            "--response_type",
            action="store",
            required=True,
            help="Response Type",
        )
        parser.add_argument(
            "--add_urls_only",
            action="store_true",
            help="if there isn't a URL then add one, otherwise do nothing",
        )
        parser.add_argument(
            "--answer_map",
            action="store",
            help="CSV mapping spreadsheet answers to GRACE answers. Columns: section, question, spreadsheet, grace",
        )

        parser.add_argument("--commit", action="store_true", help="commit things")

        parser.add_argument("--quiet", action="store_true", help="output less")

    def populate_answer_map(self):
        if self.answer_map_file is None:
            return

        df = pd.read_csv(
            self.answer_map_file,
            dtype=str,
        )

        map = defaultdict(lambda: defaultdict(dict))

        for _, row in df.iterrows():
            map[row["section"]][row["question"]][row["spreadsheet"].strip()] = row[
                "grace"
            ].strip()

        self.answer_map = map

    def populate_url_map(self):
        df = pd.read_csv(
            self.url_map_file,
        )

        for _, row in df.iterrows():
            self.url_map[row["request_url"]] = row["new_private_link"]
            # self.url_map[row["project_url"]] = row["new_private_link"]

        df = pd.read_csv(
            self.new_url_map_file,
        )

        for _, row in df.iterrows():
            self.url_map[row["request_url"].strip()] = row["new_private_link"].strip()

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
        option = option.strip()
        if (
            self.answer_map.get(q.section.title)
            and self.answer_map[q.section.title].get(q.number_and_part)
            and self.answer_map[q.section.title][q.number_and_part].get(option)
        ):
            option = self.answer_map[q.section.title][q.number_and_part][option]

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

        except Option.MultipleObjectsReturned:
            self.stderr.write(f"Multiple options “{option}‟ found for {q}")
            assert False

        return option

    def get_standard_defaults(self, name, row, details):
        notes_col = details.get("notes_column", "Additional Notes")
        notes = ""
        if row.get(notes_col) and not pd.isna(notes_col):
            notes = str(row[notes_col])

        url = self.url_map.get(row["request_url"], None)
        if url is None:
            self.print_error(
                f"no matching private url for {row['request_url']} - {row['public_body']} {name}"
            )
            url = row["request_url"]

        defaults = {
            "evidence": url,
            "public_notes": "",
            "private_notes": notes,
            "council": row["public_body"],
        }

        return defaults

    def get_defaults_for_q(self, name, q, row, details) -> Optional[dict]:
        defaults = self.get_standard_defaults(name, row, details)

        if details.get("evidence"):
            evidence = []
            if defaults.get("private_notes", "").strip() != "":
                evidence.append(defaults["private_notes"].strip())
            for col in details["evidence"]:
                if not pd.isna(row[col]):
                    s = str(row[col]).strip()
                    if s != "":
                        if details.get("skip_evidence_col_names"):
                            evidence.append("\n")
                        else:
                            evidence.append(f"\n{col}")
                        evidence.append(s)
            defaults["private_notes"] = "\n".join(evidence)

        answer_col = details.get("answer_column", "GRACE answer")
        if answer_col in row and not pd.isna(row[answer_col]):
            answer = row[answer_col].strip()
        else:
            self.print_error(f"nothing in answer column for {row['public_body']}")
            return None

        if answer.lower().strip() == "tbc":
            self.print_error(f"tbc in answer column for {row['public_body']}")
            return None

        if answer.lower().strip() == "no answer from foi":
            answer = "No response from FOI"

        option_name = "option"
        if details["type"] == "tiered":
            option_name = "multi_option"

        classification_col = "classification"
        if classification_col not in row.keys():
            classification_col = "status"

        if row[classification_col].strip() in ["Awaiting response", "Refused"]:
            defaults[option_name] = self.get_option_for_question(
                q, "No response from FOI"
            )
        elif row[classification_col] == "Data not held":
            defaults[option_name] = self.get_option_for_question(
                q, "Evidence doesn't meet criteria"
            )
        elif details["type"] == "yes_no":
            if answer == 1 or answer == "Yes":
                defaults["option"] = self.get_option_for_question(q, "Yes")
            elif answer == 0 or answer == "No":
                defaults["option"] = self.get_option_for_question(
                    q, "Evidence doesn't meet criteria"
                )
            elif answer == "Evidence doesn't meet criteria":
                defaults["option"] = self.get_option_for_question(
                    q, "Evidence doesn't meet criteria"
                )
        elif details["type"] == "multi":
            defaults["option"] = self.get_option_for_question(q, answer)
        elif details["type"] == "tiered":
            defaults["multi_option"] = self.get_option_for_question(q, answer)
        else:
            self.print_error("could not work out how to apply answer")
            return None

        return defaults

    def get_sheets(self, combined=False):
        if combined:
            ex = pd.ExcelFile(self.combined_foi_file)
        else:
            ex = pd.ExcelFile(self.foi_file)

        sheets = {}
        for sheet in ex.sheet_names:
            if sheet == "Private links to access FOIs":
                continue
            m = re.match(r"([\w&]+)\.(Q\d+)", sheet)
            if m:
                map_name = self.sheet_section_map.get(m.group(1), m.group(1))
                sheets[sheet] = f"{map_name} {m.group(2)}"
            sheets[sheet] = sheet

        return sheets

    def get_df(self, name, header=0):
        df = pd.read_excel(
            self.foi_file,
            sheet_name=name,
            header=header,
        )

        df = df.dropna(axis="index", how="all")

        return df

    def get_authority(self, authority: str, council_lookup):
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

        gss = self.gss_map.get(gss, gss)
        try:
            authority = PublicAuthority.objects.get(unique_id=gss)
        except PublicAuthority.DoesNotExist:
            self.warnings.append(f"no such authority: {orig_authority} ({authority})")
            return None

        return authority

    def get_question(self, section, details):
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

        return q

    def add_missing_urls(self, sheet_map, council_lookup, rt, u, ms):
        sheets = self.get_sheets()
        self.sheet_map = sheet_map
        for sheet, name in sheets.items():
            details = sheet_map.get(name)
            if details is None:
                continue

            if details.get("skip"):
                self.print_info(
                    f"skipping {details['section']} {details['question']} for now"
                )
                continue

            section = Section.objects.get(title=details["section"], marking_session=ms)
            q = self.get_question(section, details)

            self.print_info(f"{details['section']} {q.number_and_part}")

            df = self.get_df(sheet)
            count = 0
            missing = 0
            existing = 0
            for _, row in df.iterrows():
                authority = row["public_body"]
                authority = self.get_authority(authority, council_lookup)
                if authority is None:
                    continue

                if authority.questiongroup not in q.questiongroup.all():
                    continue

                try:
                    r = Response.objects.get(
                        authority=authority,
                        question=q,
                        response_type=rt,
                    )
                except Response.DoesNotExist:
                    missing += 1
                    continue

                if not r.public_notes and self.url_map.get(row["request_url"]):
                    r.public_notes = self.url_map.get(row["request_url"])
                    self.print_debug(
                        f"Updating URL for {section.title}, {q.number_and_part}, {authority.name}"
                    )
                    r.save()
                    count += 1
                else:
                    existing += 1

            self.print_success(
                f"updated {count} urls, {existing} already present, {missing} responses missing"
            )

    def process_sheet(
        self,
        sheet_map,
        council_lookup,
        rt,
        u,
        ms,
        combined=False,
    ):
        sheets = self.get_sheets(combined)
        self.sheet_map = sheet_map
        for sheet, name in sheets.items():
            details = sheet_map.get(name)
            if name in sheet_map.get("skip", []):
                continue

            if details is None:
                self.print_error(f"no details for [{name}]")
                continue

            if details.get("skip"):
                self.print_info(
                    f"skipping {details['section']} {details['question']} for now"
                )
                continue

            self.print_info(f"{details['section']} {details['question']}")

            self.warnings = []
            df = self.get_df(sheet, details.get("header", 0))

            section = Section.objects.get(title=details["section"], marking_session=ms)

            q = self.get_question(section, details)

            # if q.how_marked != "foi":
            # print(f"Question unexpectedly not an FOI one: {name}")
            # continue

            notes_col = details.get("notes_column", "Additional Notes")
            if notes_col not in df.columns:
                self.print_error(f"No notes column for {name}, skipping")
                continue

            answer_col = details.get("answer_column", "GRACE answer")
            if answer_col not in df.columns:
                self.print_error("no answer column, skipping")
                continue

            self.process_rows(df, name, q, details, council_lookup, rt, u)
            if len(self.warnings) > 0:
                for warning in self.warnings:
                    self.print_error(f"errors for {name}")
                    self.print_error(f" - {warning}")
                    self.print_error("---------")

    def process_rows(self, df, name, q, details, council_lookup, rt, u):
        for _, row in df.iterrows():
            defaults = self.get_defaults_for_q(name, q, row, details)
            if defaults is None:
                self.print_error(f"No defaults for {name} - {row['public_body']}")
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

    def process_q11(self, council_lookup, rt, u, ms, add_urls_only=False):
        self.warnings = []
        answers = defaultdict(dict)

        q = Question.objects.get(
            section__title="Transport", section__marking_session=ms, number=11
        )

        self.print_info("Transport Q11")

        for foi in ["roads", "airports"]:
            sheet = self.q11_map[foi]["sheet"]
            df = pd.read_excel(
                self.foi_file,
                sheet_name=sheet,
                header=0,
            )
            df = df.dropna(axis="index", how="all")
            df = df.replace("Approved roads", "Approved Roads")
            for _, row in df.iterrows():
                defaults = self.get_defaults_for_q(
                    f"Transport 11 {foi}", q, row, self.q11_map[foi]
                )
                if defaults is None:
                    self.print_error(
                        f"No defaults for Q11 {foi} - {row['public_body']}"
                    )
                    continue

                defaults["private_notes"] = f"{foi}\n{defaults['private_notes']}"
                defaults["evidence"] = f"{foi}: {defaults['evidence']}"

                authority = defaults["council"]
                del defaults["council"]

                authority = self.get_authority(authority, council_lookup)
                if authority is None:
                    continue

                all_defaults = answers[authority.name]
                if not all_defaults:
                    all_defaults["private_notes"] = defaults["private_notes"]
                else:
                    all_defaults["private_notes"] = (
                        all_defaults["private_notes"]
                        + "\n\n"
                        + defaults["private_notes"]
                    )

                if all_defaults.get("evidence"):
                    all_defaults["evidence"] = (
                        all_defaults["evidence"] + "\n" + defaults["public_notes"]
                    )
                else:
                    all_defaults["evidence"] = defaults["public_notes"]

                del defaults["public_notes"]
                del defaults["private_notes"]

                defaults[foi] = defaults["option"]
                all_defaults = {**all_defaults, **defaults}
                all_defaults["authority"] = authority
                answers[authority.name] = all_defaults

        for authority, defaults in answers.items():
            answer = []
            multi_option = []
            defaults["option"] = None
            if defaults.get("roads", None) is not None:
                answer.append(defaults["roads"])
                del defaults["roads"]
            if defaults.get("airports", None) is not None:
                answer.append(defaults["airports"])
                del defaults["airports"]

            if len(answer) == 0:
                multi_option.append(
                    Option.objects.get(question=q, description="No evidence found")
                )
            else:
                positive = False
                for yes_response in [
                    "Approved roads",
                    "Approved Roads",
                    "Approved Airports",
                ]:
                    if yes_response in [a.description for a in answer]:
                        positive = True
                        multi_option.append(
                            Option.objects.get(question=q, description=yes_response)
                        )
                if not positive:
                    for no_response in ["No response from FOI", "No evidence found"]:
                        if no_response in [a.description for a in answer]:
                            multi_option.append(
                                Option.objects.get(question=q, description=no_response)
                            )
                            break

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
            r.save()

        if len(self.warnings) > 0:
            for warning in self.warnings:
                self.print_error("errors for Transport 11")
                self.print_error(f" - {warning}")
                self.print_error("---------")

    def process_ca_q9(self, council_lookup, rt, u, ms, add_urls_only=False):
        sheet = "MA.B&H.GreenSkillsCourses (9a a"

        details = {
            "sheet": "Buildings & Heating & Skills 9",
            "section": "Buildings & Heating (MA)",
            "question": 9,
            "question_part": "a",
            "answer_column": "9a. Grace answer?",
            "notes_column": "Notes",
            "type": "tiered",
            "evidence": [
                """How many green skills/green jobs courses have been provided between 1st Sept 2021 and 1st Sept 2024?

Question 9a""",
                "If provided, please copy and paste the list of courses:",
            ],
        }
        df = pd.read_excel(
            self.foi_file,
            sheet_name=sheet,
            header=0,
        )
        df = df.dropna(axis="index", how="all")

        q9a = Question.objects.get(
            section__title="Buildings & Heating (MA)",
            section__marking_session=ms,
            number=9,
            number_part="a",
        )
        q9b = Question.objects.get(
            section__title="Buildings & Heating (MA)",
            section__marking_session=ms,
            number=9,
            number_part="b",
        )

        df = df.replace("Y", "Yes")

        details_a = details
        details_b = {
            **details,
            **{
                "question_part": "b",
                "answer_column": "9b. Grace answer?",
                "evidence": [
                    """How many people have been trained on green skills/green jobs courses between 1st Sept 2021 and 1st Sept 2024?

Question 9b"""
                ],
            },
        }

        self.print_info("Buildings & Heating (MA) Q9a&b")

        self.process_rows(df, sheet, q9a, details_a, council_lookup, rt, u)
        self.process_rows(df, sheet, q9b, details_b, council_lookup, rt, u)

    def handle(self, *args, **options):
        if options["use_csvs"]:
            self.use_csvs = True

        if options["commit"]:
            self.commit = True

        if options["quiet"]:
            self.quiet = True

        if options["answer_map"]:
            self.answer_map_file = options["answer_map"]

        response_type = options["response_type"]

        try:
            rt = ResponseType.objects.get(type=response_type)
        except ResponseType.DoesNotExist:
            self.print_error(f"No such response type: {response_type}")
            return

        ms = MarkingSession.objects.get(label="Scorecards 2027")
        u, _ = User.objects.get_or_create(
            username="FOI_importer",
        )

        # ex = pd.ExcelFile(self.foi_file)
        # print(ex.sheet_names)

        self.populate_url_map()
        self.populate_answer_map()
        council_lookup = self.get_council_lookup()

        key_map = {}
        for k, v in self.non_combined_sheet_map.items():
            key_map[k] = k[:31]

        for k, v in key_map.items():
            if k != v:
                self.non_combined_sheet_map[v] = self.non_combined_sheet_map[k]
                self.non_combined_sheet_map.pop(k)

        if not self.commit:
            self.print_info("call with --commit to save updates")

        with self.get_atomic_context(self.commit):
            if options["add_urls_only"]:
                self.add_missing_urls(
                    self.non_combined_sheet_map, council_lookup, rt, u, ms
                )
                self.add_missing_urls(
                    self.combined_sheet_map, council_lookup, rt, u, ms
                )
                self.add_missing_urls(self.q11_map, council_lookup, rt, u, ms)
                self.add_missing_urls(self.q9a_map, council_lookup, rt, u, ms)
                self.add_missing_urls(self.q9b_map, council_lookup, rt, u, ms)
            else:
                self.print_info("non combined")
                self.process_sheet(
                    self.non_combined_sheet_map,
                    council_lookup,
                    rt,
                    u,
                    ms,
                )
                self.print_info("")
                self.print_info("combined")
                self.process_sheet(
                    self.combined_sheet_map,
                    council_lookup,
                    rt,
                    u,
                    ms,
                )
                self.process_q11(
                    council_lookup, rt, u, ms, add_urls_only=options["add_urls_only"]
                )
                self.process_ca_q9(
                    council_lookup, rt, u, ms, add_urls_only=options["add_urls_only"]
                )
