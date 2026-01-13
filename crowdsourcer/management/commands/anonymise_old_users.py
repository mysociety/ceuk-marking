from django.db.models import Q

from dateutil import parser, tz

from crowdsourcer.import_utils import BaseTransactionCommand
from crowdsourcer.models import Marker


class Command(BaseTransactionCommand):
    help = "anonymise old accounts"

    domains_to_exclude = ["mysociety.org", "climateemergency.uk", "example.net"]

    def add_arguments(self, parser):
        parser.add_argument(
            "-q", "--quiet", action="store_true", help="Silence progress bars."
        )

        parser.add_argument(
            "-d",
            "--date",
            action="store",
            help="anonymise accounts created before this date, yyyy-mm-dd format",
            required=True,
        )

        parser.add_argument("--commit", action="store_true", help="commit things")

    def generate_anon_email(self, id: int):
        return f"user_{id}@example.net"

    def handle(
        self,
        quiet: bool = False,
        commit: bool = False,
        date: str = "",
        *args,
        **kwargs,
    ):
        self.quiet = quiet
        self.commit = commit
        self.verbosity = kwargs["verbosity"]

        if not self.commit:
            self.stdout.write("call with --commit to save updates")

        try:
            timezone = tz.gettz("Europe/London")
            # set a timezone to avoid naive datetime warnings
            end_date = parser.parse(date).replace(tzinfo=timezone)
        except parser.ParserError as e:
            self.stderr.write(f"Failed to parse date ({date}): {e}")
            exit(0)

        if not quiet:
            self.stdout.write(f"Anonymising all users created before {end_date}")

        count = 0
        with self.get_atomic_context(self.commit):
            users_to_anonymise = Marker.objects.filter(
                created__lt=end_date, user__email__contains="@"
            )

            exclusions = Q(user__is_staff=True) | Q(user__is_superuser=True)
            for domain in self.domains_to_exclude:
                exclusions.add(Q(user__email__endswith=domain), Q.OR)

            for marker in users_to_anonymise.exclude(exclusions).select_related("user"):
                count += 1
                if self.verbosity > 1:
                    self.stdout.write(marker.user.email)

                marker.user.email = self.generate_anon_email(marker.user.pk)
                marker.user.first_name = ""
                marker.user.last_name = ""
                marker.user.is_active = False
                marker.user.save()

        self.stdout.write(f"Anonymised {count} accounts")
