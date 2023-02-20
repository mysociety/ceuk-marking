from io import StringIO

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase

from crowdsourcer.models import Assigned


class UnassignInactiveTestCase(TestCase):
    fixtures = [
        "authorities.json",
        "basics.json",
        "users.json",
        "questions.json",
        "options.json",
        "assignments.json",
        "responses.json",
    ]

    def call_command(self, command, *args, **kwargs):
        out = StringIO()
        call_command(
            command,
            *args,
            stdout=out,
            stderr=StringIO(),
            **kwargs,
        )
        return out.getvalue()

    def test_does_not_unassign_active(self):
        self.assertEquals(Assigned.objects.count(), 3)

        self.call_command(
            "unassign_incomplete_sections_from_inactive", confirm_changes=True
        )

        self.assertEquals(Assigned.objects.count(), 3)

    def test_no_unassign_without_counfirm(self):
        self.assertEquals(Assigned.objects.count(), 3)

        u = User.objects.get(email="marker@example.org")
        u.is_active = False
        u.save()

        self.call_command("unassign_incomplete_sections_from_inactive")

        self.assertEquals(Assigned.objects.count(), 3)

    def test_unassign(self):
        self.assertEquals(Assigned.objects.count(), 3)

        u = User.objects.get(email="marker@example.org")
        u.is_active = False
        u.save()

        self.call_command(
            "unassign_incomplete_sections_from_inactive", confirm_changes=True
        )

        self.assertEquals(Assigned.objects.count(), 2)
