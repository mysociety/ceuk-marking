from django.core.management.base import BaseCommand

from crowdsourcer.marking import (
    get_assignment_progress,
    save_cached_assignment_progress,
)
from crowdsourcer.models import Assigned, MarkingSession, ResponseType

YELLOW = "\033[33m"
NOBOLD = "\033[0m"


class Command(BaseCommand):
    help = "caches current progress for a stage and session to json"

    def add_arguments(self, parser):
        parser.add_argument("--session", action="store", help="name of the session")

    def handle(self, session, *args, **kwargs):
        ms = MarkingSession.objects.get(label=session)

        for t in ResponseType.objects.all():
            qs = Assigned.objects.filter(
                marking_session=ms,
                section__isnull=False,
                active=True,
                response_type=t,
                user__is_active=True,
            )

            progress = get_assignment_progress(qs, session, t.type)
            save_cached_assignment_progress(f"{session} {t.type}", progress)
