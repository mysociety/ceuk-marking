from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db.models import Q

from crowdsourcer.models import Assigned, PublicAuthority, ResponseType, Section

YELLOW = "\033[33m"
RED = "\033[31m"
GREEN = "\033[32m"
NOBOLD = "\033[0m"

FULL_AUDIT_NUM = 40
HALF_AUDIT_NUM = 20


class Command(BaseCommand):
    help = "assign all unassigned councils in a section to a user"

    def add_arguments(self, parser):
        parser.add_argument(
            "-q", "--quiet", action="store_true", help="Silence progress bars."
        )

        parser.add_argument(
            "--commit", action="store_true", help="writes changes to db"
        )

        parser.add_argument(
            "--user",
            help="email address of user to assign remaining section councils to",
        )

        parser.add_argument(
            "--section", help="title of section to assign remaining section councils to"
        )

    def get_councils_to_assign(self, section, user):
        try:
            s = Section.objects.get(title=section)
        except Section.DoesNotExist:
            self.stdout.write(
                f"{RED}could not assign section for {user.email}, no section {section}{NOBOLD}"
            )
            return None, None

        first_mark_councils = Assigned.objects.filter(
            user=user,
            response_type=self.first_mark_rt,
            section=s,
            authority__isnull=False,
        ).values_list("authority_id", flat=True)

        assigned_councils = list(
            Assigned.objects.filter(section=s, authority__isnull=False).values_list(
                "authority_id", flat=True, response_type=self.audit_rt
            )
        )

        assigned_councils = assigned_councils + list(first_mark_councils)

        councils_to_assign = PublicAuthority.objects.exclude(
            Q(id__in=assigned_councils) | Q(type="COMB") | Q(do_not_mark=True)
        )

        if councils_to_assign.count() == 0:
            self.stdout.write(
                f"{YELLOW}No councils left in {s.title} for {user.email}{NOBOLD}"
            )

        return councils_to_assign, s

    def handle(self, quiet: bool = False, *args, **options):
        self.audit_rt = ResponseType.objects.get(type="Audit")
        self.first_mark_rt = ResponseType.objects.get(type="First Mark")

        email = options["user"]
        section = options["section"]

        try:
            user = User.objects.get(username=email)
        except User.DoesNotExist:
            self.stdout.write(
                f"{YELLOW}No user found for {email}, not attempting assignment{NOBOLD}"
            )

        councils_to_assign, s = self.get_councils_to_assign(section, user)

        if councils_to_assign is None:
            return

        if options["commit"] is True:
            self.stdout.write(
                f"{GREEN}Assigning {councils_to_assign.count()} councils in {section} to {email}{NOBOLD}"
            )
            for council in councils_to_assign:
                a, created = Assigned.objects.update_or_create(
                    user=user,
                    section=s,
                    authority=council,
                    response_type=self.audit_rt,
                )
        else:
            self.stdout.write(
                f"{YELLOW}Would assign {councils_to_assign.count()} councils in {section} to {email}{NOBOLD}"
            )

        council_count = (
            PublicAuthority.objects.filter(do_not_mark=False)
            .exclude(type="COMB")
            .count()
        )
        ca_council_count = (
            PublicAuthority.objects.filter(do_not_mark=False)
            .filter(type="COMB")
            .count()
        )
        for section in Section.objects.all():
            council_comaparison = council_count
            if section.title.find("(CA)") >= 0:
                council_comaparison = ca_council_count
            assigned = Assigned.objects.filter(
                section=section, response_type=self.audit_rt
            ).count()
            if assigned != council_comaparison:
                self.stdout.write(
                    f"{RED}Not all councils assigned for {section.title} ({assigned}/{council_comaparison}){NOBOLD}"
                )
            else:
                self.stdout.write(
                    f"{GREEN}All councils assigned for {section.title}{NOBOLD}"
                )

        volunteer_count = User.objects.all().count()
        assigned_count = (
            Assigned.objects.filter(
                user__is_superuser=False, response_type=self.audit_rt
            )
            .distinct("user_id")
            .count()
        )

        self.stdout.write(f"{assigned_count}/{volunteer_count} users assigned marking")
        if not options["commit"]:
            self.stdout.write(
                f"{YELLOW}Dry run, no assignments made, call with --commit to make them{NOBOLD}"
            )
