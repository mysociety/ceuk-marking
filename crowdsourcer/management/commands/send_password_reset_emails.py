from django.contrib.auth.forms import PasswordResetForm
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.http import HttpRequest


class Command(BaseCommand):
    help = "Emails password reset instructions to all users"

    def handle(self, *args, **kwargs):
        users = User.objects.filter(password="")
        for user in users:
            try:
                if user.email:
                    print("Sending email for to this email:", user.email)
                    form = PasswordResetForm({"email": user.email})
                    assert form.is_valid()
                    request = HttpRequest()
                    request.META["SERVER_NAME"] = "marking.councilclimatescorecards.uk"
                    request.META["SERVER_PORT"] = 443
                    form.save(
                        request=request,
                        domain_override="marking.councilclimatescorecards.uk",
                        use_https=True,
                        from_email="CEUK Scorecards Marking <climate-right-of-reply@mysociety.org>",
                        subject_template_name="registration/initial_password_email_subject.txt",
                        email_template_name="registration/initial_password_email.html",
                    )
            except Exception as e:
                print(e)
                continue

        return "done"
