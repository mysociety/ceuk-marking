from time import sleep

from django.conf import settings
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
            "--stage",
            required=True,
            action="store",
            help="Use template for this stage and only send emails to people in this stage",
        )

        parser.add_argument(
            "--session",
            action="store",
            required=True,
            help="Use this session config and only send emails to people in this session",
        )

        parser.add_argument(
            "--test_email", action="store", help="send a test email to this address"
        )

    def get_config(self, session):
        if settings.WELCOME_EMAIL.get(session):
            return settings.WELCOME_EMAIL[session]

        return None

    def get_templates(self, config, user, stage="First Mark"):
        if config.get(stage):
            config = config[stage]

        template = config["new_user_template"]
        if user.password != "":
            template = config["previous_user_template"]

        return (template, config["subject_template"])

    def handle(self, *args, **kwargs):
        if not kwargs["send_emails"]:
            self.stdout.write(
                f"{YELLOW}Not sending emails. Call with --send_emails to send{NOBOLD}"
            )

        if kwargs["test_email"]:
            users = Marker.objects.filter(
                user__email=kwargs["test_email"]
            ).select_related("user")
        else:
            users = Marker.objects.filter(send_welcome_email=True).select_related(
                "user"
            )

            if kwargs["stage"]:
                try:
                    rt = ResponseType.objects.get(type=kwargs["stage"])
                    users = users.filter(response_type=rt)
                except ResponseType.NotFoundException:
                    self.stderr.write(
                        f"{YELLOW}No such stage: {kwargs['stage']}{NOBOLD}"
                    )
                    return

            if kwargs["session"]:
                try:
                    session = MarkingSession.objects.get(label=kwargs["session"])
                    users = users.filter(marking_session=session)
                except ResponseType.NotFoundException:
                    self.stderr.write(
                        f"{YELLOW}No such session: {kwargs['session']}{NOBOLD}"
                    )
                    return

        config = self.get_config(kwargs["session"])

        if not config or len(config) == 0:
            self.stderr.write(
                f"{YELLOW}No config found for session: {kwargs['session']}{NOBOLD}"
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
                        template, subject_template = self.get_templates(
                            config, user, kwargs["stage"]
                        )
                        if user.password == "":
                            user.set_password(get_random_string(length=20))
                            user.save()

                        form = PasswordResetForm({"email": user.email})
                        assert form.is_valid()
                        request = HttpRequest()
                        request.META["SERVER_NAME"] = config["server_name"]
                        request.META["SERVER_PORT"] = 443
                        form.save(
                            request=request,
                            domain_override=config["server_name"],
                            use_https=True,
                            from_email=config["from_email"],
                            subject_template_name=subject_template,
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
