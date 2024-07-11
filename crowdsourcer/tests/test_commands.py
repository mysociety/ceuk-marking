import pathlib
from io import StringIO
from unittest import skip

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase

from crowdsourcer.models import (
    Assigned,
    Marker,
    MarkingSession,
    PublicAuthority,
    Question,
    Response,
    ResponseType,
)


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


class AssignAutomaticPoints(BaseCommandTestCase):
    fixtures = [
        "authorities.json",
        "basics.json",
        "users.json",
        "questions.json",
        "options.json",
    ]

    def test_basic_run(self):
        data_file = (
            pathlib.Path(__file__).parent.resolve() / "data" / "automatic_points.csv"
        )

        self.assertEquals(Response.objects.count(), 0)
        self.call_command(
            "add_automatic_points",
            session="Default",
            file=data_file,
            previous="Second Session",
            stage="First Mark",
            commit=True,
        )
        self.assertEquals(Response.objects.count(), 1)

        r = Response.objects.get(question_id=269)

        self.assertEquals(
            r.option.description,
            "One or more significant building have been retrofitted",
        )
        self.assertEquals(r.page_number, "322,323")
        self.assertEquals(r.public_notes, "https://www.example.org/retrofit-rules")
        self.assertEquals(r.evidence, "Awarded the point due to the Legislation")
        self.assertEquals(
            r.private_notes,
            "All District Councils get the point\nAutomatically assigned mark",
        )
        self.assertEquals(r.authority.name, "Adur District Council")

    def test_replace_answers_run(self):
        data_file = (
            pathlib.Path(__file__).parent.resolve() / "data" / "automatic_points.csv"
        )

        authority = PublicAuthority.objects.get(name="Adur District Council")
        question = Question.objects.get(id=269)
        rt = ResponseType.objects.get(type="First Mark")
        u = User.objects.get(username="marker")
        r = Response.objects.create(
            user=u,
            question=question,
            authority=authority,
            response_type=rt,
            option_id=3,
            page_number="333",
            public_notes="http://example.com/rules",
            evidence="Some evidence",
            private_notes="These are private notes",
        )

        self.assertEquals(Response.objects.count(), 1)
        self.call_command(
            "add_automatic_points",
            session="Default",
            file=data_file,
            previous="Second Session",
            stage="First Mark",
            commit=True,
            update_existing_responses=True,
        )
        self.assertEquals(Response.objects.count(), 1)

        r = Response.objects.get(question_id=269)

        self.assertEquals(
            r.option.description,
            "One or more significant building have been retrofitted",
        )
        self.assertEquals(r.page_number, "322,323")
        self.assertEquals(r.public_notes, "https://www.example.org/retrofit-rules")
        self.assertEquals(r.evidence, "Awarded the point due to the Legislation")
        self.assertEquals(
            r.private_notes,
            "All District Councils get the point\nAutomatically assigned mark\nOverridden by automatic assignment",
        )
        self.assertEquals(r.authority.name, "Adur District Council")

    def test_copy_previous_answers_run_bad_opt_match(self):
        data_file = (
            pathlib.Path(__file__).parent.resolve()
            / "data"
            / "automatic_points_copy_prev.csv"
        )

        authority = PublicAuthority.objects.get(name="Adur District Council")
        question = Question.objects.get(id=281)
        rt = ResponseType.objects.get(type="Audit")
        u = User.objects.get(username="marker")
        Response.objects.create(
            user=u,
            question=question,
            authority=authority,
            response_type=rt,
            option_id=14,
            page_number="333",
            public_notes="http://example.com/rules",
            evidence="Some evidence",
            private_notes="These are private notes",
        )

        self.assertEquals(Response.objects.count(), 1)
        self.call_command(
            "add_automatic_points",
            session="Second Session",
            file=data_file,
            previous="Default",
            stage="First Mark",
            commit=True,
        )
        self.assertEquals(Response.objects.count(), 1)

    def test_copy_previous_answers_run(self):
        data_file = (
            pathlib.Path(__file__).parent.resolve()
            / "data"
            / "automatic_points_copy_prev.csv"
        )

        opt_map = (
            pathlib.Path(__file__).parent.resolve()
            / "data"
            / "automatic_points_opt_map.csv"
        )

        authority = PublicAuthority.objects.get(name="Adur District Council")
        question = Question.objects.get(id=281)
        rt = ResponseType.objects.get(type="Audit")
        u = User.objects.get(username="marker")
        r = Response.objects.create(
            user=u,
            question=question,
            authority=authority,
            response_type=rt,
            option_id=14,
            page_number="333",
            public_notes="http://example.com/rules",
            evidence="Some evidence",
            private_notes="These are private notes",
        )

        self.assertEquals(Response.objects.count(), 1)
        self.call_command(
            "add_automatic_points",
            session="Second Session",
            file=data_file,
            option_map=opt_map,
            previous="Default",
            stage="First Mark",
            commit=True,
        )
        self.assertEquals(Response.objects.count(), 2)

        r = Response.objects.get(question_id=2002)

        self.assertEquals(
            r.option.description,
            "Section Session Transport Q1 Opt 1",
        )
        self.assertEquals(r.page_number, "333")
        self.assertEquals(r.public_notes, "http://example.com/rules")
        self.assertEquals(r.evidence, "Some evidence")
        self.assertEquals(
            r.private_notes,
            "These are private notes\nAutomatically assigned mark",
        )
        self.assertEquals(r.authority.name, "Adur District Council")

    def test_copy_and_overwrite_previous_answers(self):
        data_file = (
            pathlib.Path(__file__).parent.resolve()
            / "data"
            / "automatic_points_copy_prev_overwrite.csv"
        )

        opt_map = (
            pathlib.Path(__file__).parent.resolve()
            / "data"
            / "automatic_points_opt_map.csv"
        )

        authority = PublicAuthority.objects.get(name="Adur District Council")
        question = Question.objects.get(id=281)
        rt = ResponseType.objects.get(type="Audit")
        u = User.objects.get(username="marker")
        r = Response.objects.create(
            user=u,
            question=question,
            authority=authority,
            response_type=rt,
            option_id=14,
            page_number="333",
            public_notes="http://example.com/rules",
            evidence="Some evidence",
            private_notes="These are private notes",
        )

        self.assertEquals(Response.objects.count(), 1)
        self.call_command(
            "add_automatic_points",
            session="Second Session",
            file=data_file,
            option_map=opt_map,
            previous="Default",
            stage="First Mark",
            commit=True,
        )
        self.assertEquals(Response.objects.count(), 2)

        r = Response.objects.get(question_id=2002)

        self.assertEquals(
            r.option.description,
            "Section Session Transport Q1 Opt 1",
        )
        self.assertEquals(r.page_number, "333")
        self.assertEquals(r.public_notes, "http://example.org/some-rules")
        self.assertEquals(r.evidence, "Some evidence")
        self.assertEquals(
            r.private_notes,
            "These are private notes\nAutomatically assigned mark",
        )
        self.assertEquals(r.authority.name, "Adur District Council")

    def test_multiple_choice_question(self):
        data_file = (
            pathlib.Path(__file__).parent.resolve()
            / "data"
            / "automatic_points_multi_choice.csv"
        )
        self.assertEquals(Response.objects.count(), 0)
        self.call_command(
            "add_automatic_points",
            session="Default",
            file=data_file,
            previous="Second Session",
            stage="First Mark",
            commit=True,
        )
        self.assertEquals(Response.objects.count(), 1)
        r = Response.objects.get(question_id=282)

        self.assertIsNone(r.option)
        self.assertIsNotNone(r.multi_option)

        self.assertEquals(r.multi_option.all()[0].description, "Car share")
