import json
import math
import numbers
import re

from django.conf import settings
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

YELLOW = "\033[33m"
RED = "\033[31m"
GREEN = "\033[32m"
NOBOLD = "\033[0m"


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

    def update_responses(self, question):
        args = {
            "section__title": question["section"],
            "section__marking_session": self.session,
            "number": question["number"],
        }

        if question.get("number_part"):
            args["number_part"] = question["number_part"]

        q = Question.objects.get(**args)

        for r in Response.objects.filter(question=q, response_type=self.rt):
            if r.option:
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
                    points += question.get(o.description, 0)
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
