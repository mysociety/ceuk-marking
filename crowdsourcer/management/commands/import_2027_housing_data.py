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

    foi_file = settings.BASE_DIR / "data" / "2027" / "housing.csv"
    url_map_file = settings.BASE_DIR / "data" / "2027" / "foi-private-link-url.csv"
    new_url_map_file = (
        settings.BASE_DIR / "data" / "2027" / "updated-foi-private-link-url.csv"
    )

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

    details = [
        {
            "section": "Buildings & Heating",
            "question": 4,
            "type": "multi",
            "notes_column": "Notes",
            "evidence": [
                "Does the council manage or own more than 100 homes?",
                "How many homes does the council manage or own?",
            ],
            "answers_to_skip": [
                "Yes, 50% or above",
                "yes, 60% or above",
                "Yes, 60% or above",
                "Yes, 90% or above",
                "No response from FOI",
                "Evidence doesn't meet criteria",
                "No evidence found",
            ],
        },
        {
            "section": "Planning & Land Use",
            "question": 2,
            "type": "multi",
            "notes_column": "Notes",
            "evidence": [
                "Does the council manage or own more than 100 homes?",
                "How many homes does the council manage or own?",
            ],
            "answers_to_skip": [
                "Yes, 50% or above",
                "yes, 60% or above",
                "Yes, 60% or above",
                "Yes, 90% or above",
                "No response from FOI",
                "Evidence doesn't meet criteria",
                "No evidence found",
            ],
        },
    ]

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
            "--file",
            action="store",
            help="CSV containing the data to import",
        )
        parser.add_argument(
            "--answer_map",
            action="store",
            help="CSV mapping spreadsheet answers to GRACE answers. Columns: section, question, spreadsheet, grace",
        )

        parser.add_argument("--commit", action="store_true", help="commit things")

        parser.add_argument("--quiet", action="store_true", help="output less")

    def get_data_df(self):
        if self.data_file is None:
            return

        self.data_file = settings.BASE_DIR / "data" / self.data_file

        df = pd.read_csv(
            self.data_file,
            dtype=str,
        )
        return df

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

    def get_option_for_question(self, q, option, details):
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
            # print(f"no matching private url for {row['request_url']} - {name}")
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
            if answer in details["answers_to_skip"]:
                self.print_debug(f"Skipping answer for {row['public_body']} {answer}")
                return None
        else:
            self.print_error(f"nothing in answer column for {row['public_body']}")
            return None

        if answer.lower().strip() == "tbc":
            self.print_error(f"tbc in answer column for {row['public_body']}")
            return None

        if answer.lower().strip() == "no answer from foi":
            answer = "No response from FOI"

        if details["type"] == "yes_no":
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
            defaults["option"] = self.get_option_for_question(q, answer, details)
        elif details["type"] == "tiered":
            defaults["multi_option"] = self.get_option_for_question(q, answer)
        else:
            self.print_error("could not work out how to apply answer")
            return None

        return defaults

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

    def process_df(
        self,
        df,
        council_lookup,
        rt,
        u,
        ms,
        details,
    ):
        section = Section.objects.get(title=details["section"], marking_session=ms)

        q = self.get_question(section, details)

        notes_col = details.get("notes_column", "Additional Notes")
        if notes_col not in df.columns:
            self.print_error(f"No notes column for {section}, skipping")
            return

        answer_col = details.get("answer_column", "GRACE answer")
        if answer_col not in df.columns:
            self.print_error(f"no answer column ({answer_col}), skipping")
            return
        else:
            df[answer_col] = df[answer_col].str.strip()
            df = df[
                df[answer_col].isin(details["answers_to_skip"]) == False  # noqa: E712
            ]

        self.process_rows(df, section.title, q, details, council_lookup, rt, u)
        if len(self.warnings) > 0:
            for warning in self.warnings:
                self.print_error(f"errors for {section}")
                self.print_error(f" - {warning}")
                self.print_error("---------")

    def process_rows(self, df, name, q, details, council_lookup, rt, u):
        count = 0
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

            answer = ""
            multi_option = None
            if "multi_option" in defaults:
                multi_option = defaults["multi_option"]
                if isinstance(multi_option, Option):
                    multi_option = (multi_option,)
                defaults["option"] = None
                del defaults["multi_option"]
                answer = ",".join([o.description for o in multi_option])
            else:
                answer = defaults["option"].description

            self.print_debug(f"Adding answer for {authority} - {answer}")
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
            count += 1
        self.print_info(f"added/updated {count} responses")

    def handle(self, *args, **options):
        if options["commit"]:
            self.commit = True

        if options["quiet"]:
            self.quiet = True

        if options["answer_map"]:
            self.answer_map_file = options["answer_map"]

        response_type = options["response_type"]
        self.data_file = options["file"]

        try:
            rt = ResponseType.objects.get(type=response_type)
        except ResponseType.DoesNotExist:
            self.print_error(f"No such response type: {response_type}")
            return

        ms = MarkingSession.objects.get(label="Scorecards 2027")
        u, _ = User.objects.get_or_create(
            username="FOI_importer",
        )

        self.populate_url_map()
        self.populate_answer_map()
        council_lookup = self.get_council_lookup()

        if not self.commit:
            self.print_info("call with --commit to save updates")

        df = self.get_data_df()

        with self.get_atomic_context(self.commit):
            if options["add_urls_only"]:
                self.add_missing_urls(
                    self.non_combined_sheet_map, council_lookup, rt, u, ms
                )
            else:
                for details in self.details:
                    self.print_info(f"processing {details['section']}")
                    self.process_df(
                        df,
                        council_lookup,
                        rt,
                        u,
                        ms,
                        details,
                    )
