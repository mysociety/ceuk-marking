from django.contrib.auth.models import User

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

        parser.add_argument("--commit", action="store_true", help="commit things")

    def get_session(self, name):
        session = None
        try:
            session = MarkingSession.objects.get(label=name)
        except MarkingSession.DoesNotExist as e:
            self.errors.append(f"No such marking session: {name}")

        return session

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
        self.old_q = self.get_question(q, s, self.old_session)
        self.new_q = self.get_question(q, s, self.new_session)

    def process(self):
        councils = PublicAuthority.objects.filter(marking_session=self.new_ms)

        responses = Response.objects.filter(
            question=self.old_q, authority__in=councils, response_type=self.old_rt
        )

        for r in responses:
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

            if r.option:
                try:
                    new_opt = Option.objects.get(
                        question=self.new_q, description=r.option.description
                    )
                except Option.DoesNotExist:
                    self.print_error(f"No matching option for {r.option.description}")
                    continue

                new_r.option = new_opt
            else:
                for o in r.multi_option.all():
                    try:
                        new_opt = Option.objects.get(
                            question=self.new_q, description=o.description
                        )
                    except Option.DoesNotExist:
                        self.print_error(f"No matching option for {o.description}")
                        continue

                    new_r.multi_option.add(new_opt)

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
