from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

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
