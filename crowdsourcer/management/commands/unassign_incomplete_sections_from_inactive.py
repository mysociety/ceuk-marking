from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db.models import F, Q

from crowdsourcer.models import Assigned, PublicAuthority, Question, Section


class Command(BaseCommand):
    help = "unassign incomplete sections from inactive users"

    yellow = "\x1b[33;20m"
    reset = "\x1b[0m"

    def add_arguments(self, parser):
        parser.add_argument(
            "--confirm_changes", action="store_true", help="make updates to database"
        )

    def handle(self, *args, **kwargs):
        users = User.objects.filter(is_active=False)

        sections = Section.objects.all()

        if kwargs["confirm_changes"] is False:
            self.stdout.write(
                f"{self.yellow}call with --confirm_changes to update database{self.reset}"
            )

        for section in sections:
            questions = Question.objects.filter(section=section)

            responses = PublicAuthority.response_counts(
                questions, section.title, None
            ).filter(
                Q(num_questions__gt=F("num_responses")) | Q(num_responses__isnull=True)
            )

            to_unassign = Assigned.objects.filter(
                section=section, user__in=users, authority__in=responses
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