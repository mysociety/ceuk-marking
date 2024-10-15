from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

import pandas as pd

from crowdsourcer.models import (
    MarkingSession,
    Option,
    PublicAuthority,
    Question,
    QuestionGroup,
    Response,
    ResponseType,
    Section,
)


class Command(BaseCommand):
    help = "set up some helpful data for testing"

    question_list = (
        settings.BASE_DIR / "crowdsourcer" / "fixtures" / "test_data_questions.csv"
    )
    responses_list = (
        settings.BASE_DIR / "crowdsourcer" / "fixtures" / "test_data_responses.csv"
    )

    marking_sessions = ["Session One", "Session Two"]
    groups = ["Single Tier", "District", "County", "Northern Ireland"]

    sections = [
        "First Section",
        "Second Section",
    ]

    areas = [
        {
            "name": "Test Council",
            "type": "CTY",
            "gss": "E100001",
        },
        {
            "name": "Example Council",
            "type": "CTY",
            "gss": "E100002",
        },
    ]

    response_types = ["First Mark", "Right of Reply", "Audit"]

    def add_arguments(self, parser):
        parser.add_argument(
            "-q", "--quiet", action="store_true", help="Silence progress bars."
        )

    def get_group(self, props):
        group = "District"

        print(props["name"], props["type"])
        if props["type"] == "LGD":
            group = "Northern Ireland"
        elif props["type"] in ["CC", "MTD", "LBO", "UTA"]:
            group = "Single Tier"
        elif props["type"] in ["CTY"]:
            group = "County"

        g = QuestionGroup.objects.get(description=group)
        return g

    def add_questions(self):
        df = pd.read_csv(self.question_list)
        for _, question in df.iterrows():
            sections = Section.objects.filter(title=question["section"]).all()
            defaults = {
                "description": question["question"],
                "criteria": question["criteria"],
                "question_type": question["type"],
                "clarifications": question["clarifications"],
            }

            for section in sections:
                q, c = Question.objects.update_or_create(
                    number=int(question["number"]),
                    section=section,
                    defaults=defaults,
                )

                if q.question_type in ["select_one", "tiered", "multiple_choice"]:
                    o, c = Option.objects.update_or_create(
                        question=q,
                        description="None",
                        defaults={"score": 0, "ordering": 100},
                    )

                    for i in range(1, 4):
                        desc = question[f"option_{i}"]
                        score = 1
                        ordering = i

                        o, c = Option.objects.update_or_create(
                            question=q,
                            description=desc,
                            defaults={"score": score, "ordering": ordering},
                        )
                elif q.question_type == "yes_no":
                    for desc in ["Yes", "No"]:
                        ordering = 1
                        score = 1
                        if desc == "No":
                            score = 0
                            ordering = 2
                        o, c = Option.objects.update_or_create(
                            question=q,
                            description=desc,
                            defaults={"score": score, "ordering": ordering},
                        )

                for group in QuestionGroup.objects.all():
                    q.questiongroup.add(group)

            for section in Section.objects.filter(marking_session__label="Session Two"):
                prev_section = Section.objects.get(
                    title=section.title, marking_session__label="Session One"
                )
                for question in Question.objects.filter(section=section):
                    prev_question = Question.objects.get(
                        number=question.number, section=prev_section
                    )
                    question.previous_question = prev_question
                    question.save()

    def add_responses(self):
        df = pd.read_csv(self.responses_list)
        for _, response in df.iterrows():
            question = Question.objects.get(
                number=response["number"],
                section=Section.objects.get(
                    title=response["section"],
                    marking_session__label=response["session"],
                ),
            )

            stage = ResponseType.objects.get(type=response["stage"])
            authority = PublicAuthority.objects.get(name=response["authority"])
            defaults = {
                "public_notes": response["public_notes"],
                "page_number": response["page_number"],
                "evidence": response["evidence"],
                "private_notes": response["private_notes"],
                "user": self.user,
            }

            if stage.type != "Right of Reply":
                option = Option.objects.get(
                    question=question, description=response["answer"]
                )

                defaults["option"] = option
            else:
                defaults["agree_with_response"] = False
                if response["agree_with_response"] == "Yes":
                    defaults["agree_with_response"] = True

            _, r = Response.objects.update_or_create(
                question=question,
                authority=authority,
                response_type=stage,
                defaults=defaults,
            )

    def handle(self, quiet: bool = False, *args, **options):

        for group in self.groups:
            g, c = QuestionGroup.objects.update_or_create(description=group)

        for r_type in self.response_types:
            r, c = ResponseType.objects.update_or_create(type=r_type, priority=1)

        stage = ResponseType.objects.get(type="First Mark")

        for session in self.marking_sessions:
            m, c = MarkingSession.objects.update_or_create(
                label=session,
                defaults={"active": True, "stage": stage, "start_date": "2024-10-01"},
            )

            for section in self.sections:
                s, c = Section.objects.update_or_create(
                    title=section, marking_session=m
                )

            for group in QuestionGroup.objects.all():
                group.marking_session.add(m)

        m.default = True
        m.save()

        for area in self.areas:
            defaults = {
                "name": area["name"],
                "questiongroup": self.get_group(area),
                "do_not_mark": False,
                "type": area["type"],
            }

            a, created = PublicAuthority.objects.update_or_create(
                unique_id=area["gss"],
                defaults=defaults,
            )

            for session in MarkingSession.objects.all():
                a.marking_session.add(session)

        self.user, _ = User.objects.get_or_create(username="test_data_user@example.com")

        self.add_questions()
        self.add_responses()
