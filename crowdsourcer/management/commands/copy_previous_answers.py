from collections import defaultdict

from django.contrib.auth.models import User

import pandas as pd

from crowdsourcer.import_utils import BaseImporter
from crowdsourcer.models import (
    MarkingSession,
    Option,
    PublicAuthority,
    Question,
    Response,
    ResponseType,
)


class Command(BaseImporter):
    help = "copy final responses from one session to another"

    quiet = True
    commit = False
    errors = []

    ma_sessions = ["Scorecards 2027"]

    def add_arguments(self, parser):
        parser.add_argument(
            "--verbose", action="store_true", help="say more about what is happening"
        )

        parser.add_argument(
            "--old", action="store", help="sesion to copy answers from", required=True
        )
        parser.add_argument(
            "--new", action="store", help="sesion to copy answers to", required=True
        )
        parser.add_argument(
            "--question",
            action="store",
            help="question to copy answers from",
            required=True,
        )
        parser.add_argument(
            "--section",
            action="store",
            help="section to copy answers from",
            required=True,
        )
        # this should be a csv file with section, q, old description, new description columns
        parser.add_argument(
            "--response_map",
            action="store",
            help="csv map from old q responses to new ones",
        )

        parser.add_argument("--commit", action="store_true", help="commit things")

    def get_session(self, name):
        session = None
        try:
            session = MarkingSession.objects.get(label=name)
        except MarkingSession.DoesNotExist:
            self.errors.append(f"No such marking session: {name}")

        return session

    def get_new_section(self, section, session):
        if session in self.ma_sessions:
            section = section.replace("(CA)", "(MA)")

        return section

    def get_response_map(self, file):
        if file == "" or file is None:
            return {}

        df = pd.read_csv(file)
        df.question = df.question.astype(str)

        option_map = defaultdict(dict)
        for _, option in df.iterrows():
            if option_map[option["section"]].get(option["question"]) is None:
                option_map[option["section"]][option["question"]] = {}

            option_map[option["section"]][option["question"]][option["prev_option"]] = (
                option["new_option"]
            )

        return option_map

    def get_mapped_answer(self, answer, q, answer_map):
        if (
            answer_map.get(q.section.title) is not None
            and answer_map[q.section.title].get(q.number_and_part) is not None
            and answer_map[q.section.title][q.number_and_part].get(answer) is not None
        ):
            return answer_map[q.section.title][q.number_and_part][answer]

        return answer

    def get_question(self, q, section, session):
        q = Question.get_question_from_number_and_part(q, section, session)

        if q is None:
            self.errors.append(
                f"No such question {q} ({section}) for session {session}"
            )

        return q

    def setup(self, options):
        self.user, _ = User.objects.get_or_create(
            username="Auto_answer_script",
        )
        self.old_rt = ResponseType.objects.get(type="Audit")
        self.new_rt = ResponseType.objects.get(type="First Mark")

        self.old_session = options["old"]
        self.new_session = options["new"]

        self.old_ms = self.get_session(self.old_session)
        self.new_ms = self.get_session(self.new_session)

        q = options["question"]
        s = options["section"]
        new_s = self.get_new_section(s, self.new_session)
        self.old_q = self.get_question(q, s, self.old_session)
        self.new_q = self.get_question(q, new_s, self.new_session)

        self.response_map = self.get_response_map(options["response_map"])

    def process(self):
        councils = PublicAuthority.objects.filter(marking_session=self.new_ms)

        if self.old_q.question_type != self.new_q.question_type:
            self.print_error("Question types do not match")
            return

        responses = Response.objects.filter(
            question=self.old_q, authority__in=councils, response_type=self.old_rt
        )

        for r in responses:
            option = None
            options = []
            if r.option:
                try:
                    new_opt = Option.objects.get(
                        question=self.new_q,
                        description=self.get_mapped_answer(
                            r.option.description, self.old_q, self.response_map
                        ),
                    )
                except Option.DoesNotExist:
                    self.print_error(f"No matching option for {r.option.description}")
                    continue

                option = new_opt
            else:
                for o in r.multi_option.all():
                    try:
                        new_opt = Option.objects.get(
                            question=self.new_q,
                            description=self.get_mapped_answer(
                                o.description, self.old_q, self.response_map
                            ),
                        )
                    except Option.DoesNotExist:
                        self.print_error(f"No matching option for {o.description}")
                        continue

                    options.append(new_opt)

            new_r, _ = Response.objects.get_or_create(
                question=self.new_q,
                authority=r.authority,
                response_type=self.new_rt,
                defaults={
                    "user": self.user,
                    "public_notes": r.public_notes,
                    "evidence": r.evidence,
                    "page_number": r.page_number,
                    "private_notes": r.private_notes,
                },
            )

            if option:
                new_r.option = option
            else:
                for o in options:
                    new_r.multi_option.add(o)

            new_r.save()

            if not self.quiet:
                self.print_info(f"added question to {r.authority.name}")

    def handle(self, *args, **options):
        if options["commit"]:
            self.commit = True

        if options["verbose"]:
            self.quiet = False

        if not self.commit:
            self.print_info("call with --commit to save updates")

        self.setup(options)

        if self.errors:
            for e in self.errors:
                self.print_error(e)
            exit()

        with self.get_atomic_context(self.commit):
            self.process()
