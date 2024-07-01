from collections import defaultdict

from django.core.management.base import BaseCommand

import pandas as pd

from crowdsourcer.models import MarkingSession, Question, Section


class Command(BaseCommand):
    help = "set up question links to previous session"

    overrides = {}

    def add_arguments(self, parser):
        parser.add_argument(
            "--current",
            action="store",
            required=True,
            help="The current session",
        )

        parser.add_argument(
            "--previous",
            action="store",
            required=True,
            help="The previous session",
        )

        parser.add_argument(
            "--overrides", action="store", help="CSV file with list of link overrides"
        )

    def get_overrides(self, file):
        df = pd.read_csv(file)

        overrides = defaultdict(dict)
        for _, row in df.iterrows():
            overrides[row["section"]][str(row["current_question"])] = str(
                row["previous_question"]
            )

        self.overrides = overrides

    def get_session(self, session_label):
        try:
            ms = MarkingSession.objects.get(label=session_label)
        except MarkingSession.DoesNotExist:
            ms = None

        return ms

    def setup_sessions(self, *args, **kwargs):
        setup = True

        for session in ("current", "previous"):
            ms = self.get_session(kwargs[session])
            if ms is not None:
                setattr(self, session, ms)
            else:
                setup = False
                self.stderr.write(
                    f"Could not find {session} session: {kwargs[session]}"
                )

        return setup

    def get_questions(self, session):
        questions = defaultdict(dict)

        for section in Section.objects.filter(marking_session=session):
            for question in Question.objects.filter(section=section).order_by("pk"):
                if questions[section.title].get(question.number_and_part) is None:
                    questions[section.title][question.number_and_part] = question

        return questions

    def handle(self, *args, **kwargs):
        sessions_exist = self.setup_sessions(*args, **kwargs)
        if not sessions_exist:
            return

        if kwargs.get("overrides") is not None:
            self.get_overrides(kwargs["overrides"])

        current_questions = self.get_questions(self.current)
        previous_questions = self.get_questions(self.previous)

        for section, questions in current_questions.items():
            for q_no, question in questions.items():
                overrides = self.overrides.get(section, None)
                if overrides is not None and overrides.get(q_no) is not None:
                    prev_question_no = overrides.get(q_no, q_no)
                    self.stdout.write(
                        f"Using previous question {prev_question_no} for {question} in {section}"
                    )
                else:
                    prev_question_no = q_no

                if previous_questions[section].get(prev_question_no) is None:
                    self.stderr.write(f"No matching question for {q_no} in {section}")
                    continue
                else:
                    prev_question = previous_questions[section][prev_question_no]

                question.previous_question = prev_question
                question.save()
