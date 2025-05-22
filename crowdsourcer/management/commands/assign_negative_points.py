import json

from django.conf import settings
from django.contrib.auth.models import User

from crowdsourcer.import_utils import BaseImporter
from crowdsourcer.models import (
    MarkingSession,
    Question,
    Response,
    ResponseType,
)


class Command(BaseImporter):
    help = "assigns negative points based on existing answers"

    def add_arguments(self, parser):
        parser.add_argument(
            "-q", "--quiet", action="store_true", help="Silence debug data."
        )

        parser.add_argument(
            "--session",
            action="store",
            required=True,
            help="Marking session to use questions with",
        )

        parser.add_argument(
            "--config",
            action="store",
            required=True,
            help="JSON file containing the configuration for national points",
        )

        parser.add_argument(
            "--commit",
            action="store_true",
            help="Save the responses to the database",
        )

    def get_question(self, details):
        args = {
            "section__title": details["section"],
            "section__marking_session": self.session,
            "number": details["number"],
        }

        if details.get("number_part"):
            args["number_part"] = details["number_part"]

        try:
            q = Question.objects.get(**args)
        except Question.DoesNotExist:
            q = None

        return q

    def update_responses(self, question):
        q = self.get_question(question)

        for r in Response.objects.filter(question=q, response_type=self.rt):
            points_map = None
            if question.get("dependent_q"):
                dependent_q = self.get_question(question["dependent_q"])

                if dependent_q:
                    try:
                        dependent_r = Response.objects.get(
                            authority=r.authority,
                            response_type=self.rt,
                            question=dependent_q,
                        )
                        points_map = question["points_map"].get(
                            dependent_r.option.description,
                            question["points_map"]["default"],
                        )
                    except Response.DoesNotExist:
                        points_map = question["points_map"]["default"]
                else:
                    points_map = question["points_map"]["default"]

                points_map = points_map.get(
                    r.authority.country,
                    points_map.get(r.authority.type, points_map["default"]),
                )
            elif (
                question.get("points_map_councils")
                and r.authority.name in question["points_map_councils"]
            ):
                points_map = question["points_map"]["council"]

            if r.option:
                if points_map:
                    points = points_map.get(r.option.description, 0)
                else:
                    points = question.get(r.option.description, 0)
                self.print_debug(
                    f"updating {q.number_and_part} for {r.authority} to {points}"
                )
                r.points = points
                r.user = self.user
                r.save()
            elif r.multi_option:
                points = 0
                for o in r.multi_option.all():
                    if points_map:
                        points += points_map.get(o.description, 0)
                    else:
                        points += question.get(o.description, 0)
                self.print_debug(
                    f"updating {q.number_and_part} for {r.authority} to {points}"
                )
                r.points = points
                r.user = self.user
                r.save()

    def handle(
        self,
        quiet: bool = False,
        commit: bool = False,
        *args,
        **kwargs,
    ):
        self.quiet = quiet

        self.commit = commit
        self.config_file = settings.BASE_DIR / "data" / kwargs["config"]

        with open(self.config_file) as conf_file:
            config = json.load(conf_file)

        self.rt = ResponseType.objects.get(type="Audit")
        self.session = MarkingSession.objects.get(label=kwargs["session"])

        if not self.commit:
            self.print_info("Not saving any responses, run with --commit to do so")

        with self.get_atomic_context(self.commit):
            user, _ = User.objects.get_or_create(username="Negative_Updater")
            self.user = user
            for question in config["questions"]:
                self.update_responses(question)
