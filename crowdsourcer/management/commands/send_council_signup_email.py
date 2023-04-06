from time import sleep

from django.contrib.auth.forms import PasswordResetForm
from django.core.management.base import BaseCommand
from django.http import HttpRequest
from django.utils.crypto import get_random_string

from crowdsourcer.models import Marker

YELLOW = "\033[33m"
NOBOLD = "\033[0m"


class Command(BaseCommand):
    help = "Emails password reset instructions to council users"

    def add_arguments(self, parser):
        parser.add_argument("--send_emails", action="store_true", help="Send emails")

    def handle(self, *args, **kwargs):
        if not kwargs["send_emails"]:
            self.stdout.write(
                f"{YELLOW}Not sending emails. Call with --send_emails to send{NOBOLD}"
            )

        council_users = Marker.objects.filter(
            user__password="", response_type__type="Right of Reply"
        )
        user_count = council_users.count()
        self.stdout.write(f"Sending emails for {user_count} councils")
        count = 0
        for council in council_users:
            user = council.user
            try:
                if user.email:
                    self.stdout.write(f"Sending email for to this email: {user.email}")
                    if kwargs["send_emails"]:
                        user.set_password(get_random_string(length=20))
                        user.save()
                        form = PasswordResetForm({"email": user.email})
                        assert form.is_valid()
                        request = HttpRequest()
                        request.META[
                            "SERVER_NAME"
                        ] = "marking.councilclimatescorecards.uk"
                        request.META["SERVER_PORT"] = 443
                        form.save(
                            request=request,
                            domain_override="marking.councilclimatescorecards.uk",
                            use_https=True,
                            from_email="CEUK Scorecards Marking <climate-right-of-reply@mysociety.org>",
                            subject_template_name="registration/council_password_email_subject.txt",
                            email_template_name="registration/council_password_email.html",
                        )
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
