from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from crowdsourcer.models import Assigned, Marker, ResponseType

YELLOW = "\033[33m"
NOBOLD = "\033[0m"


class Command(BaseCommand):
    help = "Sets audit volunteers to active"

    def add_arguments(self, parser):
        parser.add_argument("--commit", action="store_true", help="commits DB change")

    def handle(self, *args, **kwargs):
        if not kwargs["commit"]:
            self.stdout.write(
                f"{YELLOW}Not commiting changes. Call with --commit to update database{NOBOLD}"
            )
        users_to_be_made_auditors = (
            Assigned.objects.filter(response_type__type="Audit")
            .values_list("user", flat=True)
            .distinct()
        )
        self.stdout.write(
            f"{len(users_to_be_made_auditors) - User.objects.filter(marker__response_type__type='Audit').count()} users to be made into auditors."
        )
        if kwargs["commit"]:
            rt = ResponseType.objects.get(type="Audit")
            Marker.objects.filter(user__id__in=users_to_be_made_auditors).update(
                response_type=rt
            )

        users = User.objects.filter(
            marker__response_type__type="Audit", is_active=False
        )
        user_count = users.count()
        self.stdout.write(f"Activating {user_count} users")
        if kwargs["commit"]:
            update_count = users.update(is_active=True)

        if kwargs["commit"]:
            self.stdout.write(f"Activated {update_count} users")
        else:
            self.stdout.write(
                f"{YELLOW}Dry Run{NOBOLD}. Live would have activated {user_count} users"
            )

        return "done"
