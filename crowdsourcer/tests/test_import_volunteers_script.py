import pathlib
from io import StringIO

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase

from crowdsourcer.models import (
    Assigned,
    Marker,
    MarkingSession,
    PublicAuthority,
    ResponseType,
    Section,
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


class AssignVolunteers(BaseCommandTestCase):
    fixtures = [
        "authorities.json",
        "basics.json",
        "questions.json",
        "options.json",
    ]

    def add_extra_councils(self):
        councils = [
            ("East Borsetshire", "E90001"),
            ("West Borsetshire", "E90002"),
            ("North Borsetshire", "E90003"),
            ("South Borsetshire", "E90004"),
            ("Upper Borsetshire", "E90005"),
            ("Lower Borsetshire", "E90006"),
            ("Mid Borsetshire", "E90007"),
            ("Old Borsetshire", "E90008"),
        ]

        ms = MarkingSession.objects.get(label="Default")
        for council in councils:
            a = PublicAuthority.objects.create(
                name=council[0],
                country="england",
                unique_id=council[1],
                type="DIS",
                questiongroup_id=2,
            )
            a.marking_session.set([ms])

    def test_no_add_users(self):
        data_file = pathlib.Path(__file__).parent.resolve() / "data" / "volunteers.csv"

        self.assertEquals(User.objects.count(), 0)
        self.assertEquals(Marker.objects.count(), 0)
        self.assertEquals(Assigned.objects.count(), 0)
        self.call_command(
            "import_volunteers",
            session="Default",
            file=data_file,
        )
        self.assertEquals(User.objects.count(), 0)
        self.assertEquals(Marker.objects.count(), 0)
        self.assertEquals(Assigned.objects.count(), 0)

    def test_no_add_assignments(self):
        data_file = pathlib.Path(__file__).parent.resolve() / "data" / "volunteers.csv"

        self.assertEquals(User.objects.count(), 0)
        self.assertEquals(Marker.objects.count(), 0)
        self.assertEquals(Assigned.objects.count(), 0)
        self.call_command(
            "import_volunteers",
            session="Default",
            file=data_file,
            add_users=True,
        )
        self.assertEquals(User.objects.count(), 1)
        self.assertEquals(Marker.objects.count(), 1)
        self.assertEquals(Assigned.objects.count(), 0)

    def test_basic_run(self):
        data_file = pathlib.Path(__file__).parent.resolve() / "data" / "volunteers.csv"

        self.assertEquals(User.objects.count(), 0)
        self.assertEquals(Marker.objects.count(), 0)
        self.assertEquals(Assigned.objects.count(), 0)
        self.call_command(
            "import_volunteers",
            session="Default",
            file=data_file,
            add_users=True,
            make_assignments=True,
        )
        self.assertEquals(User.objects.count(), 1)
        self.assertEquals(Marker.objects.count(), 1)
        self.assertEquals(Assigned.objects.count(), 2)
        self.assertEquals(
            Assigned.objects.filter(
                marking_session__label="Default", section__title="Transport"
            ).count(),
            2,
        )

        u = User.objects.all()[0]
        m = Marker.objects.all()[0]
        self.assertEquals(u.username, "first_last@example.org")
        self.assertEquals(m.response_type.type, "First Mark")

        councils = [a.authority.name for a in Assigned.objects.all()]
        self.assertTrue("Aberdeenshire Council" not in councils)
        self.assertTrue("Aberdeen City Council" in councils)
        self.assertTrue("Adur District Council" in councils)

    def test_dry_run(self):
        data_file = pathlib.Path(__file__).parent.resolve() / "data" / "volunteers.csv"

        self.assertEquals(User.objects.count(), 0)
        self.assertEquals(Marker.objects.count(), 0)
        self.assertEquals(Assigned.objects.count(), 0)
        self.call_command(
            "import_volunteers",
            session="Default",
            file=data_file,
            add_users=True,
            make_assignments=True,
            dry_run=True,
        )
        self.assertEquals(User.objects.count(), 0)
        self.assertEquals(Marker.objects.count(), 0)
        self.assertEquals(Assigned.objects.count(), 0)

    def test_multi_councils(self):
        data_file = (
            pathlib.Path(__file__).parent.resolve()
            / "data"
            / "volunteers_two_councils.csv"
        )

        self.assertEquals(Assigned.objects.count(), 0)
        self.call_command(
            "import_volunteers",
            session="Default",
            file=data_file,
            add_users=True,
            make_assignments=True,
        )
        self.assertEquals(Assigned.objects.count(), 1)

        councils = [a.authority.name for a in Assigned.objects.all()]
        self.assertTrue("Aberdeenshire Council" not in councils)
        self.assertTrue("Aberdeen City Council" not in councils)
        self.assertTrue("Adur District Council" in councils)

    def test_assignment_limits(self):
        data_file = pathlib.Path(__file__).parent.resolve() / "data" / "volunteers.csv"
        self.add_extra_councils()

        self.assertEquals(Assigned.objects.count(), 0)
        self.call_command(
            "import_volunteers",
            session="Default",
            file=data_file,
            add_users=True,
            make_assignments=True,
        )
        self.assertEquals(User.objects.count(), 1)
        self.assertEquals(Marker.objects.count(), 1)
        self.assertEquals(Assigned.objects.count(), 6)
        self.assertEquals(
            Assigned.objects.filter(
                marking_session__label="Default", section__title="Transport"
            ).count(),
            6,
        )

    def test_alt_columns(self):
        data_file = (
            pathlib.Path(__file__).parent.resolve() / "data" / "volunteers_alt.csv"
        )
        col_file = (
            pathlib.Path(__file__).parent.resolve() / "data" / "volunteer_cols.csv"
        )

        self.assertEquals(User.objects.count(), 0)
        self.assertEquals(Marker.objects.count(), 0)
        self.assertEquals(Assigned.objects.count(), 0)
        self.call_command(
            "import_volunteers",
            session="Default",
            file=data_file,
            col_names=col_file,
            add_users=True,
            make_assignments=True,
        )
        self.assertEquals(User.objects.count(), 1)
        self.assertEquals(Marker.objects.count(), 1)
        self.assertEquals(Assigned.objects.count(), 2)
        self.assertEquals(
            Assigned.objects.filter(
                marking_session__label="Default", section__title="Transport"
            ).count(),
            2,
        )

    def test_multiple_assignments(self):
        data_file = (
            pathlib.Path(__file__).parent.resolve() / "data" / "volunteers_multiple.csv"
        )
        self.add_extra_councils()

        Section.objects.exclude(title="Transport").delete()

        self.assertEquals(Assigned.objects.count(), 0)
        out = self.call_command(
            "import_volunteers",
            session="Default",
            file=data_file,
            add_users=True,
            make_assignments=True,
        )
        self.assertEquals(User.objects.count(), 2)
        self.assertEquals(Marker.objects.count(), 2)
        self.assertEquals(Assigned.objects.count(), 11)
        self.assertEquals(
            Assigned.objects.filter(
                marking_session__label="Default", section__title="Transport"
            ).count(),
            11,
        )

        self.assertEquals(
            Assigned.objects.filter(
                marking_session__label="Default",
                user__username="first_last@example.org",
            ).count(),
            6,
        )

        self.assertEquals(
            Assigned.objects.filter(
                marking_session__label="Default",
                user__username="primary_secondary@example.org",
            ).count(),
            5,
        )

        self.assertRegex(out, r"All councils and sections assigned")
        self.assertRegex(out, r"2/2 users assigned marking")

    def test_skip_bad_own_council(self):
        data_file = (
            pathlib.Path(__file__).parent.resolve() / "data" / "volunteers_multiple.csv"
        )
        self.add_extra_councils()

        PublicAuthority.objects.get(name="Aberdeen City Council").delete()

        self.assertEquals(Assigned.objects.count(), 0)
        out = self.call_command(
            "import_volunteers",
            session="Default",
            file=data_file,
            add_users=True,
            make_assignments=True,
        )
        self.assertEquals(User.objects.count(), 2)
        self.assertEquals(Marker.objects.count(), 2)
        self.assertEquals(Assigned.objects.count(), 6)

        self.assertEquals(
            Assigned.objects.filter(
                marking_session__label="Default",
                user__username="primary_secondary@example.org",
            ).count(),
            0,
        )

        self.assertRegex(out, r"Bad council: Aberdeen City Council")

    def test_skip_assignments_if_existing(self):
        data_file = pathlib.Path(__file__).parent.resolve() / "data" / "volunteers.csv"

        self.call_command(
            "import_volunteers",
            session="Default",
            file=data_file,
            add_users=True,
        )

        u = User.objects.get(username="first_last@example.org")
        s = Section.objects.get(title="Transport", marking_session__label="Default")
        a = PublicAuthority.objects.get(name="Aberdeen City Council")
        rt = ResponseType.objects.get(type="First Mark")
        ms = MarkingSession.objects.get(label="Default")

        Assigned.objects.create(
            user=u,
            section=s,
            authority=a,
            response_type=rt,
            marking_session=ms,
        )

        self.assertEquals(Assigned.objects.count(), 1)
        out = self.call_command(
            "import_volunteers",
            session="Default",
            file=data_file,
            add_users=True,
            make_assignments=True,
        )
        self.assertEquals(Assigned.objects.count(), 1)
        self.assertRegex(out, r"Existing assignments: first_last@example.org")

    def test_not_all_councils_warning(self):
        data_file = pathlib.Path(__file__).parent.resolve() / "data" / "volunteers.csv"

        self.add_extra_councils()

        out = self.call_command(
            "import_volunteers",
            session="Default",
            file=data_file,
            add_users=True,
            make_assignments=True,
        )
        self.assertEquals(Assigned.objects.count(), 6)
        self.assertRegex(out, r"Not all councils assigned for Transport \(6/11\)")

    def test_not_all_users_warning(self):
        data_file = pathlib.Path(__file__).parent.resolve() / "data" / "volunteers.csv"

        PublicAuthority.objects.get(name="Aberdeen City Council").delete()
        PublicAuthority.objects.get(name="Adur District Council").delete()

        out = self.call_command(
            "import_volunteers",
            session="Default",
            file=data_file,
            add_users=True,
            make_assignments=True,
        )
        self.assertEquals(Assigned.objects.count(), 0)
        self.assertRegex(
            out, r"No councils left in Transport for first_last@example.org"
        )

    def test_bad_section_warning(self):
        data_file = pathlib.Path(__file__).parent.resolve() / "data" / "volunteers.csv"

        Section.objects.filter(title="Transport").delete()

        out = self.call_command(
            "import_volunteers",
            session="Default",
            file=data_file,
            add_users=True,
            make_assignments=True,
        )
        self.assertEquals(Assigned.objects.count(), 0)
        self.assertRegex(
            out,
            r"could not assign section for first_last@example.org, no section Transport",
        )

    def test_assignment_map(self):
        data_file = pathlib.Path(__file__).parent.resolve() / "data" / "volunteers.csv"
        assigment_file = (
            pathlib.Path(__file__).parent.resolve()
            / "data"
            / "volunteers_assignment_map.csv"
        )

        self.add_extra_councils()

        self.call_command(
            "import_volunteers",
            session="Default",
            file=data_file,
            assignment_map=assigment_file,
            add_users=True,
            make_assignments=True,
        )
        self.assertEquals(Assigned.objects.count(), 4)

    def test_council_map(self):
        data_file = pathlib.Path(__file__).parent.resolve() / "data" / "volunteers.csv"
        assigment_file = (
            pathlib.Path(__file__).parent.resolve()
            / "data"
            / "volunteers_council_assignment_map.csv"
        )

        PublicAuthority.objects.get(name="Aberdeenshire Council").delete()

        self.call_command(
            "import_volunteers",
            session="Default",
            file=data_file,
            authority_map=assigment_file,
            add_users=True,
            make_assignments=True,
        )
        self.assertEquals(Assigned.objects.count(), 1)
        councils = [a.authority.name for a in Assigned.objects.all()]
        self.assertTrue("Aberdeenshire Council" not in councils)
        self.assertTrue("Adur District Council" not in councils)
        self.assertTrue("Aberdeen City Council" in councils)

    def test_assignment_limits_in_file(self):
        data_file = (
            pathlib.Path(__file__).parent.resolve()
            / "data"
            / "volunteers_with_limit.csv"
        )
        self.add_extra_councils()

        self.assertEquals(Assigned.objects.count(), 0)
        self.call_command(
            "import_volunteers",
            session="Default",
            file=data_file,
            add_users=True,
            make_assignments=True,
            assignment_count_in_data=True,
        )
        self.assertEquals(User.objects.count(), 1)
        self.assertEquals(Marker.objects.count(), 1)
        self.assertEquals(Assigned.objects.count(), 3)
        self.assertEquals(
            Assigned.objects.filter(
                marking_session__label="Default", section__title="Transport"
            ).count(),
            3,
        )

    def test_council_preferences(self):
        data_file = (
            pathlib.Path(__file__).parent.resolve()
            / "data"
            / "volunteers_with_council_restriction.csv"
        )
        self.add_extra_councils()

        self.assertEquals(Assigned.objects.count(), 0)
        self.call_command(
            "import_volunteers",
            session="Default",
            file=data_file,
            add_users=True,
            make_assignments=True,
            preferred_councils=True,
        )
        self.assertEquals(User.objects.count(), 1)
        self.assertEquals(Marker.objects.count(), 1)
        self.assertEquals(Assigned.objects.count(), 6)
        self.assertEquals(
            Assigned.objects.filter(
                marking_session__label="Default", section__title="Transport"
            ).count(),
            6,
        )

        councils = [a.authority.name for a in Assigned.objects.all()]
        self.assertTrue("Aberdeen City Council" not in councils)

        # need to remove them all as won't assign to people with existing assignments
        Assigned.objects.all().delete()

        ob = PublicAuthority.objects.get(unique_id="E90001")
        ob.type = "LBO"
        ob.save()

        PublicAuthority.objects.filter(
            unique_id__in=("E90004", "E90005", "E90006", "E90007")
        ).delete()

        self.call_command(
            "import_volunteers",
            session="Default",
            file=data_file,
            add_users=True,
            make_assignments=True,
            preferred_councils=True,
        )
        self.assertEquals(User.objects.count(), 1)
        self.assertEquals(Marker.objects.count(), 1)
        self.assertEquals(Assigned.objects.count(), 6)
        self.assertEquals(
            Assigned.objects.filter(
                marking_session__label="Default", section__title="Transport"
            ).count(),
            6,
        )

        councils = [a.authority.name for a in Assigned.objects.all()]
        self.assertTrue("East Borsetshire" in councils)
        self.assertTrue("Aberdeen City Council" in councils)

    def test_audit_assignments(self):
        data_file = pathlib.Path(__file__).parent.resolve() / "data" / "volunteers.csv"

        self.assertEquals(User.objects.count(), 0)
        self.assertEquals(Marker.objects.count(), 0)
        self.assertEquals(Assigned.objects.count(), 0)
        self.call_command(
            "import_volunteers",
            session="Default",
            response_type="Audit",
            file=data_file,
            add_users=True,
            make_assignments=True,
        )
        self.assertEquals(User.objects.count(), 1)
        self.assertEquals(Marker.objects.count(), 1)
        self.assertEquals(Assigned.objects.count(), 2)
        self.assertEquals(
            Assigned.objects.filter(
                marking_session__label="Default",
                section__title="Transport",
                response_type__type="Audit",
            ).count(),
            2,
        )

        u = User.objects.all()[0]
        m = Marker.objects.all()[0]
        self.assertEquals(u.username, "first_last@example.org")
        self.assertEquals(m.response_type.type, "Audit")

        councils = [a.authority.name for a in Assigned.objects.all()]
        self.assertTrue("Aberdeenshire Council" not in councils)
        self.assertTrue("Aberdeen City Council" in councils)
        self.assertTrue("Adur District Council" in councils)

    def test_audit_assignments_avoids_previous_assignments(self):
        data_file = pathlib.Path(__file__).parent.resolve() / "data" / "volunteers.csv"

        self.call_command(
            "import_volunteers",
            session="Default",
            file=data_file,
            add_users=True,
            make_assignments=True,
        )

        Assigned.objects.all().delete()

        u = User.objects.get(username="first_last@example.org")
        s = Section.objects.get(title="Transport", marking_session__label="Default")
        a = PublicAuthority.objects.get(name="Aberdeen City Council")
        rt = ResponseType.objects.get(type="First Mark")
        ms = MarkingSession.objects.get(label="Default")

        Assigned.objects.create(
            user=u,
            section=s,
            authority=a,
            response_type=rt,
            marking_session=ms,
        )

        self.call_command(
            "import_volunteers",
            session="Default",
            response_type="Audit",
            file=data_file,
            add_users=True,
            make_assignments=True,
        )
        self.assertEquals(User.objects.count(), 1)
        self.assertEquals(Marker.objects.count(), 1)
        self.assertEquals(Assigned.objects.count(), 2)
        self.assertEquals(
            Assigned.objects.filter(
                marking_session__label="Default",
                section__title="Transport",
                response_type__type="Audit",
            ).count(),
            1,
        )

        u = User.objects.all()[0]
        m = Marker.objects.all()[0]
        self.assertEquals(u.username, "first_last@example.org")
        self.assertEquals(m.response_type.type, "Audit")

        councils = [
            a.authority.name
            for a in Assigned.objects.filter(response_type__type="Audit")
        ]
        self.assertTrue("Aberdeenshire Council" not in councils)
        self.assertTrue("Aberdeen City Council" not in councils)
        self.assertTrue("Adur District Council" in councils)
