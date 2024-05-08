import pathlib
from io import StringIO
from unittest import skip

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase

from crowdsourcer.models import Assigned, Marker, MarkingSession, Response


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

    def setUp(self):
        self.session = MarkingSession.objects.get(label="Default")

    def test_does_not_unassign_active(self):
        self.assertEquals(
            Assigned.objects.filter(marking_session=self.session).count(), 4
        )

        self.call_command(
            "unassign_incomplete_sections_from_inactive",
            confirm_changes=True,
            stage="First Mark",
            session="Default",
        )

        self.assertEquals(
            Assigned.objects.filter(marking_session=self.session).count(), 4
        )

    def test_no_unassign_without_counfirm(self):
        self.assertEquals(
            Assigned.objects.filter(marking_session=self.session).count(), 4
        )

        u = User.objects.get(email="marker@example.org")
        u.is_active = False
        u.save()

        self.call_command(
            "unassign_incomplete_sections_from_inactive",
            stage="First Mark",
            session="Default",
        )

        self.assertEquals(
            Assigned.objects.filter(marking_session=self.session).count(), 4
        )

    def test_unassign(self):
        self.assertEquals(
            Assigned.objects.filter(marking_session=self.session).count(), 4
        )

        u = User.objects.get(email="marker@example.org")
        u.is_active = False
        u.save()

        self.call_command(
            "unassign_incomplete_sections_from_inactive",
            confirm_changes=True,
            stage="First Mark",
            session="Default",
        )

        self.assertEquals(
            Assigned.objects.filter(marking_session=self.session).count(), 2
        )


@skip("need to fix adding marking session with assigment")
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


class RemoveIdenticalDuplicatesTestCase(BaseCommandTestCase):
    fixtures = [
        "authorities.json",
        "basics.json",
        "users.json",
        "questions.json",
        "options.json",
        "assignments.json",
        "audit_responses.json",
        "audit_duplicate_responses.json",
    ]

    def test_deduplicate(self):
        self.assertEquals(Response.objects.count(), 21)
        self.call_command("remove_identical_duplicates", session="Default")
        self.assertEquals(Response.objects.count(), 21)

        self.call_command("remove_identical_duplicates", commit=True, session="Default")
        self.assertEquals(Response.objects.count(), 18)

        for pk in [16, 19, 25]:
            self.assertFalse(Response.objects.filter(pk=pk).exists())


class UpdateExMultiOptionQs(BaseCommandTestCase):
    fixtures = [
        "authorities.json",
        "basics.json",
        "users.json",
        "questions.json",
        "options.json",
        "assignments.json",
        "audit_responses.json",
        "audit_ex_multi_option_responses.json",
    ]

    def test_nocommit(self):
        option_count = Response.objects.filter(option__isnull=False).count()
        self.assertEquals(option_count, 8)
        multi_option_count = Response.objects.filter(multi_option__isnull=False).count()
        self.assertEquals(multi_option_count, 5)

        self.call_command("update_ex_multi_option_qs")

        option_count = Response.objects.filter(option__isnull=False).count()
        self.assertEquals(option_count, 8)
        multi_option_count = Response.objects.filter(multi_option__isnull=False).count()
        self.assertEquals(multi_option_count, 5)

    def test_deduplicate(self):
        option_count = Response.objects.filter(option__isnull=False).count()
        self.assertEquals(option_count, 8)
        multi_option_count = Response.objects.filter(multi_option__isnull=False).count()
        self.assertEquals(multi_option_count, 5)

        r = Response.objects.get(id=16)
        self.assertEquals(r.option_id, None)
        self.assertEquals(r.multi_option.count(), 1)

        r = Response.objects.get(id=17)
        self.assertEquals(r.option_id, None)
        self.assertEquals(r.multi_option.count(), 2)

        r = Response.objects.get(id=18)
        self.assertEquals(r.option_id, None)
        self.assertEquals(r.multi_option.count(), 1)

        r = Response.objects.get(id=19)
        self.assertEquals(r.option_id, 161)
        self.assertEquals(r.multi_option.count(), 1)

        out = self.call_command(
            "update_ex_multi_option_qs", commit=True, session="Default"
        )

        option_count = Response.objects.filter(option__isnull=False).count()
        self.assertEquals(option_count, 10)
        multi_option_count = Response.objects.filter(multi_option__isnull=False).count()
        self.assertEquals(multi_option_count, 3)

        r = Response.objects.get(id=16)
        self.assertEquals(r.option_id, 161)
        self.assertEquals(r.multi_option.count(), 0)

        r = Response.objects.get(id=17)
        self.assertEquals(r.option_id, None)
        self.assertEquals(r.multi_option.count(), 2)

        r = Response.objects.get(id=18)
        self.assertEquals(r.option_id, 162)
        self.assertEquals(r.multi_option.count(), 0)

        r = Response.objects.get(id=19)
        self.assertEquals(r.option_id, 161)
        self.assertEquals(r.multi_option.count(), 1)

        YELLOW = "\033[33m"
        GREEN = "\033[32m"
        NOBOLD = "\033[0m"

        self.assertEquals(
            out,
            f"""examining 4 responses
{YELLOW}multiple response 17, Aberdeenshire Council Buildings & Heating 9{NOBOLD}
{YELLOW}existing response 19, Adur District Council Buildings & Heating 9{NOBOLD}
updated 2 items for Buildings & Heating: 9
{GREEN}done{NOBOLD}
""",
        )
