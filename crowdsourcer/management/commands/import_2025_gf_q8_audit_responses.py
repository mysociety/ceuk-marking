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
    help = "update GF Q8/9 data"

    commit = False
    quiet = True
    sheet_map = None
    added = 0
    updated = 0

    file = settings.BASE_DIR / "data" / "scorecards-2025" / "gf_q8_audit_responses.xlsx"

    warnings = []

    sheets = {
        "Gov&Finance.Q8.Climatestaff": {
            "section": "Governance & Finance",
            "question": 8,
            "type": "multi",
            "twfy-project": 14,
            "include_notes_col_names": True,
            "notes": [
                "Please copy and paste the list of roles:",
            ],
        },
    }
    combined_sheet_map = {
        "Gov&Finance.Q8.Climatestaff": {
            "section": "Governance & Finance (CA)",
            "question": 9,
            "type": "multi",
            "twfy-project": 14,
            "include_notes_col_names": True,
            "notes": [
                "Please copy and paste the list of roles:",
            ],
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
            "--verbose", action="store_true", help="say more about what is happening"
        )
        parser.add_argument("--commit", action="store_true", help="commit things")

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

    def get_standard_defaults(self, name, row):
        notes = ""
        if row.get("Additional Notes") and not pd.isna(row["Additional Notes"]):
            notes = str(row["Additional Notes"])

        url = row["Private link to access FOIs"]

        defaults = {
            "evidence": url,
            "private_notes": notes,
            "public_notes": row["public_notes"],
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
        elif q_details["type"] == "multi":
            if name == "G&F Q8":
                defaults["option"] = self.get_gf_8_answer(q, row, value)
        else:
            self.warnings.append(
                f"could not get default answer for {row['public_body']}"
            )
            return None

        return defaults

    def get_sheets(self, combined=False):
        ex = pd.ExcelFile(self.file)

        sheets = {}
        for sheet in ex.sheet_names:
            sheets[sheet] = sheet

        return sheets

    def get_df(self, name):
        df = pd.read_excel(
            self.file,
            sheet_name=name,
            header=1,
        )

        # make the column name less unwieldy
        old_name = df.columns[18]
        df = df.rename(columns={old_name: "public_notes"})
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
        self.added = 0
        self.updated = 0
        for sheet, name in sheets.items():
            details = sheet_map.get(name)

            self.print_info(f"{details['section']} {details['question']}")

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

            if "Notes" not in df.columns and not details.get("notes"):
                self.print_error(f"No notes column for {name}, skipping")
                self.print_error("---------")
                continue

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

                if authority.questiongroup not in q.questiongroup.all():
                    continue

                if not defaults.get("public_notes") or not defaults.get(
                    "private_notes"
                ):
                    prev_r = Response.objects.get(
                        question=q,
                        response_type__type="First Mark",
                        authority=authority,
                    )
                    if not defaults.get("notes"):
                        self.print_debug(f"using prev notes for {authority}")
                        defaults["public_notes"] = prev_r.public_notes

                    if not defaults.get("private_notes"):
                        self.print_debug(f"using prev private notes for {authority}")
                        defaults["private_notes"] = prev_r.private_notes

                multi_option = None
                if "multi_option" in defaults:
                    multi_option = defaults["multi_option"]
                    if isinstance(multi_option, Option):
                        multi_option = (multi_option,)
                    defaults["option"] = None
                    del defaults["multi_option"]

                r, created = Response.objects.update_or_create(
                    question=q,
                    authority=authority,
                    response_type=rt,
                    user=u,
                    defaults=defaults,
                )

                if created:
                    self.added += 1
                else:
                    self.updated += 1

                if multi_option is not None:
                    r.multi_option.set(multi_option)
                else:
                    r.multi_option.clear()

            if len(self.warnings) > 0:
                for warning in self.warnings:
                    self.print_error(f"errors for {name}")
                    self.print_error(f" - {warning}")
                    self.print_error("---------")

            if self.commit:
                self.print_success(
                    f"{self.added} responses added, {self.updated} responses updated"
                )
            else:
                self.print_info(
                    f"would of added {self.added} and updated {self.updated} responses"
                )

    def handle(self, *args, **options):
        if options["commit"]:
            self.commit = True

        if options["verbose"]:
            self.quiet = False

        if not self.commit:
            self.print_info("call with --commit to save updates")

        rt = ResponseType.objects.get(type="Audit")
        ms = MarkingSession.objects.get(label="Scorecards 2025")
        council_lookup = self.get_council_lookup()

        with self.get_atomic_context(self.commit):
            u, _ = User.objects.get_or_create(
                username="FOI_importer",
            )
            self.process_sheet(self.sheets, council_lookup, rt, u, ms)
            self.process_sheet(self.combined_sheet_map, council_lookup, rt, u, ms)
