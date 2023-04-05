import pathlib
from io import StringIO

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase

from crowdsourcer.models import Assigned, Marker


class BaseCommandTestCase(TestCase):
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


class UnassignInactiveTestCase(BaseCommandTestCase):
    fixtures = [
        "authorities.json",
        "basics.json",
        "users.json",
        "questions.json",
        "options.json",
        "assignments.json",
        "responses.json",
    ]

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

        self.assertEquals(Assigned.objects.count(), 1)


class ImportCouncilsTestCase(BaseCommandTestCase):
    fixtures = [
        "authorities.json",
        "basics.json",
    ]

    def test_import_councils_no_commit(self):
        data_file = (
            pathlib.Path(__file__).parent.resolve() / "data" / "merged_contacts.csv"
        )

        self.call_command("import_councils", council_list=data_file)

        self.assertEquals(0, Assigned.objects.count())
        self.assertEquals(0, Marker.objects.count())

    def test_import_councils(self):
        data_file = (
            pathlib.Path(__file__).parent.resolve() / "data" / "merged_contacts.csv"
        )

        self.call_command("import_councils", add_users=True, council_list=data_file)

        self.assertEquals(2, User.objects.count())
        self.assertEquals(2, Assigned.objects.count())
        self.assertEquals(2, Marker.objects.count())

        adur_user = User.objects.get(username="adur@example.org")
        self.assertEquals("Adur District Council", adur_user.marker.authority.name)

        aberdeen_user = User.objects.get(username="aberdeen@example.org")
        assigments = Assigned.objects.filter(user=aberdeen_user).order_by(
            "authority__name"
        )

        self.assertEquals(assigments[0].authority.name, "Aberdeen City Council")
        self.assertEquals(assigments[1].authority.name, "Aberdeenshire Council")
        self.assertEquals(assigments[0].section, None)

        self.assertFalse(
            Marker.objects.filter(
                authority__name="Armagh City, Banbridge and Craigavon Borough Council"
            ).exists()
        )

        self.assertFalse(User.objects.filter(username="armagh@example.org").exists())
