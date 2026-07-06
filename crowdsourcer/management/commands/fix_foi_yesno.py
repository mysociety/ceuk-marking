from crowdsourcer.import_utils import BaseImporter
from crowdsourcer.models import MarkingSession, Option, Question


class Command(BaseImporter):
    help = "Add missing no response option to yes/no FOI questions"

    commit = False
    quiet = True

    def add_arguments(self, parser):
        parser.add_argument(
            "--session",
            required=True,
            action="store",
            help="Marking session to use questions with",
        )

        parser.add_argument("--verbose", action="store_true", help="more output")
        parser.add_argument("--commit", action="store_true", help="commit things")

    def handle(self, *args, **options):
        if options["commit"]:
            self.commit = True

        if options["verbose"]:
            self.quiet = False

        ms = MarkingSession.objects.get(label="Scorecards 2027")

        with self.get_atomic_context(self.commit):
            questions = Question.objects.filter(
                section__marking_session=ms,
                how_marked="foi",
                question_type="yes_no",
            )

            for q in questions:
                options = Option.objects.filter(question=q).values_list(
                    "description", flat=True
                )
                if "No response from FOI" not in options:
                    self.print_info(f"Adding option to {q}")

                    Option.objects.create(
                        question=q,
                        description="No response from FOI",
                        score=0,
                        ordering=3,
                    )
