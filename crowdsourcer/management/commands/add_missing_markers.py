from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from crowdsourcer.models import Assigned, Marker, MarkingSession, ResponseType

YELLOW = "\033[33m"
NOBOLD = "\033[0m"


class Command(BaseCommand):
    help = "Make sure all user's have a related Marker"

    rts = ["First Mark", "Right of Reply", "Audit"]

    def add_arguments(self, parser):
        parser.add_argument(
            "--session", required=True, action="store", help="Marking session to use"
        )

    def handle(self, *args, **kwargs):
        users = User.objects.filter(marker__isnull=True)

        session_label = kwargs["session"]

        session = MarkingSession.objects.get(label=session_label)

        for user in users:
            assigned = list(
                Assigned.objects.filter(user=user)
                .values_list("response_type__type", flat=True)
                .distinct()
            )

            num_rts = len(assigned)
            if num_rts == 0:
                rt_type = "First Mark"
            elif len(assigned) == 1:
                rt_type = assigned[0]
            else:
                for rt in self.rts:
                    if rt in assigned:
                        rt_type = rt

            if rt_type is None:
                rt_type = "First Mark"

            m = Marker.objects.create(
                user=user,
                response_type=ResponseType.objects.get(type=rt_type),
            )
            m.marking_session.add(session)

        print(f"Added markers to {users.count()} users")
