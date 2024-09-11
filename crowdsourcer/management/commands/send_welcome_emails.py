from time import sleep

from django.contrib.auth.forms import PasswordResetForm
from django.core.management.base import BaseCommand
from django.http import HttpRequest
from django.utils.crypto import get_random_string

from crowdsourcer.models import Marker, MarkingSession, ResponseType

YELLOW = "\033[33m"
NOBOLD = "\033[0m"


class Command(BaseCommand):
    help = "Emails password reset instructions to all users"

    new_user_template = "registration/initial_password_email.html"
    previous_user_template = "registration/repeat_password_email.html"

    def add_arguments(self, parser):
        parser.add_argument("--send_emails", action="store_true", help="Send emails")

        parser.add_argument(
            "--stage", action="store", help="Only send emails to people in this stage"
        )

        parser.add_argument(
            "--session",
            action="store",
            help="Only send emails to people in this session",
        )

    def handle(self, *args, **kwargs):
        if not kwargs["send_emails"]:
            self.stdout.write(
                f"{YELLOW}Not sending emails. Call with --send_emails to send{NOBOLD}"
            )

        users = Marker.objects.filter(send_welcome_email=True).select_related("user")

        if kwargs["stage"]:
            try:
                rt = ResponseType.objects.get(type=kwargs["stage"])
                users = users.filter(response_type=rt)
            except ResponseType.NotFoundException:
                self.stderr.write(f"{YELLOW}No such stage: {kwargs['stage']}{NOBOLD}")
                return

        if kwargs["session"]:
            try:
                rt = MarkingSession.objects.get(label=kwargs["session"])
                users = users.filter(marking_session=rt)
            except ResponseType.NotFoundException:
                self.stderr.write(
                    f"{YELLOW}No such session: {kwargs['session']}{NOBOLD}"
                )
                return

        user_count = users.count()
        self.stdout.write(f"Sending emails for {user_count} users")
        count = 0
        for marker in users:
            user = marker.user
            try:
                if user.email:
                    self.stdout.write(f"Sending email for to this email: {user.email}")
                    if kwargs["send_emails"]:
                        template = self.new_user_template
                        if user.password == "":
                            user.set_password(get_random_string(length=20))
                            user.save()
                        else:
                            template = self.previous_user_template

                        form = PasswordResetForm({"email": user.email})
                        assert form.is_valid()
                        request = HttpRequest()
                        request.META["SERVER_NAME"] = (
                            "marking.councilclimatescorecards.uk"
                        )
                        request.META["SERVER_PORT"] = 443
                        form.save(
                            request=request,
                            domain_override="marking.councilclimatescorecards.uk",
                            use_https=True,
                            from_email="CEUK Scorecards Marking <climate-right-of-reply@mysociety.org>",
                            subject_template_name="registration/initial_password_email_subject.txt",
                            email_template_name=template,
                        )
                        marker.send_welcome_email = False
                        marker.save()
                        sleep(1)
                    count = count + 1
            except Exception as e:
                print(e)
                continue

        if kwargs["send_emails"]:
            self.stdout.write(f"Sent {count} emails")
        else:
            self.stdout.write(
                f"{YELLOW}Dry Run{NOBOLD}. Live would have sent {count} emails"
            )

        return "done"