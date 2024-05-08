from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db.models import F, Q

from crowdsourcer.models import (
    Assigned,
    MarkingSession,
    PublicAuthority,
    Question,
    ResponseType,
    Section,
)


class Command(BaseCommand):
    help = "unassign incomplete sections from inactive users"

    yellow = "\x1b[33;20m"
    reset = "\x1b[0m"

    def add_arguments(self, parser):
        parser.add_argument(
            "--confirm_changes", action="store_true", help="make updates to database"
        )

        parser.add_argument(
            "--stage", required=True, help="which stage of assignments to remove"
        )

        parser.add_argument(
            "--session",
            action="store",
            help="Marking session to remove assignments from",
        )

    def handle(self, *args, **kwargs):
        session_label = kwargs.get("session", None)
        try:
            session = MarkingSession.objects.get(label=session_label)
        except MarkingSession.DoesNotExist:
            self.stderr.write(f"No session with that name: {session_label}")
            return

        stage = kwargs["stage"]
        stage = ResponseType.objects.get(type=stage)

        users = User.objects.filter(is_active=False)

        sections = Section.objects.filter(marking_session=session)

        if kwargs["confirm_changes"] is False:
            self.stdout.write(
                f"{self.yellow}call with --confirm_changes to update database{self.reset}"
            )

        for section in sections:
            questions = Question.objects.filter(section=section)

            responses = PublicAuthority.response_counts(
                questions, section.title, None, session
            ).filter(
                Q(num_questions__gt=F("num_responses")) | Q(num_responses__isnull=True)
            )

            to_unassign = Assigned.objects.filter(
                section=section,
                user__in=users,
                authority__in=responses,
                response_type=stage,
                marking_session=session,
            ).order_by("authority__name")

            if to_unassign.count() > 0:
                self.stdout.write(
                    f"unassigning following authorities for section {section.title}"
                )
                for authority in to_unassign:
                    self.stdout.write("   " + authority.authority.name)

                if kwargs["confirm_changes"] is True:
                    to_unassign.delete()
            else:
                self.stdout.write(
                    f"no authorities to unassign for section {section.title}"
                )

        return "done"
