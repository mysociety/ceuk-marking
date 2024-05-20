import pathlib

from django.contrib.auth.models import Permission, User
from django.test import TestCase
from django.urls import reverse

from crowdsourcer.models import Assigned, MarkingSession, ResponseType, Section


class BaseTestCase(TestCase):
    fixtures = [
        "authorities.json",
        "basics.json",
        "users.json",
        "questions.json",
        "options.json",
        "assignments.json",
    ]

    def setUp(self):
        p = Permission.objects.get(codename="can_manage_users")
        u = User.objects.get(username="volunteer_admin")
        u.user_permissions.add(p)

        self.client.force_login(u)
        self.user = u


class TestAccess(TestCase):
    fixtures = [
        "authorities.json",
        "basics.json",
        "users.json",
    ]

    user_id = 3
    urls = [
        "list_volunteers",
        "available_authorities",
        "bulk_assign_volunteer",
    ]
    user_urls = [
        "assign_volunteer",
        "edit_volunteer",
    ]

    def test_no_anon_access(self):
        for url in self.urls:
            url = reverse(url)
            response = self.client.get(url)
            self.assertEqual(response.status_code, 302)
            self.assertEqual(response.url, f"/accounts/login/?next={url}")

        for url in self.user_urls:
            url = reverse(url, args=(self.user_id,))
            response = self.client.get(url)
            self.assertEqual(response.status_code, 302)
            self.assertEqual(response.url, f"/accounts/login/?next={url}")

    def test_access_with_no_permissions(self):
        u = User.objects.get(username="other_marker")
        self.client.force_login(u)
        for url in self.urls:
            url = reverse(url)
            response = self.client.get(url)
            self.assertEqual(response.status_code, 403)

        for url in self.user_urls:
            url = reverse(url, args=(self.user_id,))
            response = self.client.get(url)
            self.assertEqual(response.status_code, 403)

    def test_access_with_permissions(self):
        p = Permission.objects.get(codename="can_manage_users")
        u = User.objects.get(username="volunteer_admin")
        u.user_permissions.add(p)

        self.client.force_login(u)
        for url in self.urls:
            url = reverse(url)
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)

        for url in self.user_urls:
            url = reverse(url, args=(self.user_id,))
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)


class TestListVolunteers(BaseTestCase):
    def test_shows_assignments(self):
        url = reverse("list_volunteers")
        response = self.client.get(url)

        context = response.context

        volunteers = context["volunteers"]
        self.assertEqual(len(volunteers), 3)

        emails = [u.email for u in volunteers]
        self.assertTrue("marker@example.org" in emails)
        self.assertTrue("council@example.org" in emails)
        self.assertTrue("auditor@example.org" in emails)
        self.assertTrue("other_marker@example.org" not in emails)

        v = volunteers[0]

        self.assertEqual(v.email, "auditor@example.org")
        self.assertEqual(v.marker.response_type.type, "Audit")
        self.assertEqual(v.num_assignments, 1)

        v = volunteers[1]

        self.assertEqual(v.email, "council@example.org")
        self.assertEqual(v.marker.response_type.type, "Right of Reply")
        self.assertEqual(v.num_assignments, None)

        v = volunteers[2]

        self.assertEqual(v.email, "marker@example.org")
        self.assertEqual(v.marker.response_type.type, "First Mark")
        self.assertEqual(v.num_assignments, 3)


class TestEditVolunteer(BaseTestCase):
    def test_other_session_user(self):
        url = reverse("edit_volunteer", args=("5",))
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_no_op_edit(self):
        url = reverse("edit_volunteer", args=("2",))
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        u = response.context["form"].instance

        self.assertEqual(u.email, "marker@example.org")

        response = self.client.post(
            url,
            data={
                "marker-INITIAL_FORMS": 1,
                "marker-MAX_NUM_FORMS": 1,
                "marker-MIN_NUM_FORMS": 0,
                "marker-TOTAL_FORMS": 1,
                "marker-0-id": u.marker.pk,
                "marker-0-user": u.pk,
                "first_name": u.first_name,
                "last_name": u.last_name,
                "email": u.email,
                "username": u.username,
                "marker-0-response_type": u.marker.response_type.pk,
            },
        )

        self.assertRedirects(response, f"/Default{reverse('list_volunteers')}")

    def test_edit(self):
        url = reverse("edit_volunteer", args=("2",))
        response = self.client.get(url)
        u = response.context["form"].instance

        self.assertEqual(u.marker.response_type.type, "First Mark")

        rt = ResponseType.objects.get(type="Audit")

        response = self.client.post(
            url,
            data={
                "marker-INITIAL_FORMS": 1,
                "marker-MAX_NUM_FORMS": 1,
                "marker-MIN_NUM_FORMS": 0,
                "marker-TOTAL_FORMS": 1,
                "marker-0-id": u.marker.pk,
                "marker-0-user": u.pk,
                "first_name": u.first_name,
                "last_name": u.last_name,
                "email": u.email,
                "username": u.username,
                "marker-0-response_type": rt.pk,
            },
        )

        self.assertRedirects(response, f"/Default{reverse('list_volunteers')}")

        u = User.objects.get(id=2)
        self.assertEqual(u.marker.response_type.type, "Audit")


class TestBulkAssign(BaseTestCase):
    def test_assignments(self):
        url = reverse("bulk_assign_volunteer")
        response = self.client.get(url)

        self.assertEqual(
            Assigned.objects.filter(marking_session__label="Default").count(), 4
        )
        self.assertEqual(
            Assigned.objects.filter(marking_session__label="Second Session").count(), 1
        )

        volunteer_file = (
            pathlib.Path(__file__).parent.resolve() / "data" / "test_volunteers.xlsx"
        )
        with open(volunteer_file, "rb") as fp:
            response = self.client.post(
                url,
                data={
                    "volunteer_list": fp,
                    "response_type": "First Mark",
                    "session": "Default",
                    "num_assignments": 2,
                },
            )

        self.assertRedirects(response, f"/Default{reverse('list_volunteers')}")
        # only adds 2 as there are only two councils
        self.assertEqual(
            Assigned.objects.filter(marking_session__label="Default").count(), 6
        )
        self.assertEqual(
            Assigned.objects.filter(marking_session__label="Second Session").count(), 1
        )

    def test_force_assignments(self):
        url = reverse("bulk_assign_volunteer")
        response = self.client.get(url)

        self.assertEqual(
            Assigned.objects.filter(marking_session__label="Default").count(), 4
        )

        volunteer_file = (
            pathlib.Path(__file__).parent.resolve() / "data" / "test_volunteers.xlsx"
        )
        with open(volunteer_file, "rb") as fp:
            response = self.client.post(
                url,
                data={
                    "volunteer_list": fp,
                    "response_type": "First Mark",
                    "session": "Default",
                    "num_assignments": 10,
                    "always_assign": True,
                },
            )

        self.assertRedirects(response, f"/Default{reverse('list_volunteers')}")
        # only adds 2 as there are only two councils
        self.assertEqual(
            Assigned.objects.filter(marking_session__label="Default").count(), 6
        )

    def test_not_enough_volunteers_warning(self):
        url = reverse("bulk_assign_volunteer")
        response = self.client.get(url)

        self.assertEqual(Assigned.objects.count(), 5)

        volunteer_file = (
            pathlib.Path(__file__).parent.resolve() / "data" / "test_volunteers.xlsx"
        )
        with open(volunteer_file, "rb") as fp:
            response = self.client.post(
                url,
                data={
                    "volunteer_list": fp,
                    "response_type": "First Mark",
                    "session": "Default",
                    "num_assignments": 10,
                },
            )

        self.assertEqual(response.status_code, 200)
        form = response.context["form"]

        self.assertEqual(
            form.errors["__all__"][0],
            "Too many volunteers for Transport, not all volunteers will get assignments. Need 2.0 per volunteer.",
        )

        self.assertEqual(Assigned.objects.count(), 5)

    def test_not_enough_councils_warning(self):
        url = reverse("bulk_assign_volunteer")
        response = self.client.get(url)

        self.assertEqual(Assigned.objects.count(), 5)

        volunteer_file = (
            pathlib.Path(__file__).parent.resolve() / "data" / "test_volunteers.xlsx"
        )
        with open(volunteer_file, "rb") as fp:
            response = self.client.post(
                url,
                data={
                    "volunteer_list": fp,
                    "response_type": "First Mark",
                    "session": "Default",
                    "num_assignments": 1,
                },
            )

        self.assertEqual(response.status_code, 200)
        form = response.context["form"]

        self.assertEqual(
            form.errors["__all__"][0],
            "Not enough volunteers for Transport, not all entities will have volunteers - 1.0 more volunteers needed.",
        )

        self.assertEqual(Assigned.objects.count(), 5)

    def test_bad_section_warning(self):
        s = Section.objects.get(title="Transport", marking_session__label="Default")
        s.title = "Not Transport"
        s.save()

        url = reverse("bulk_assign_volunteer")
        response = self.client.get(url)

        self.assertEqual(Assigned.objects.count(), 5)

        volunteer_file = (
            pathlib.Path(__file__).parent.resolve() / "data" / "test_volunteers.xlsx"
        )
        with open(volunteer_file, "rb") as fp:
            response = self.client.post(
                url,
                data={
                    "volunteer_list": fp,
                    "response_type": "First Mark",
                    "session": "Default",
                    "num_assignments": 1,
                },
            )

        self.assertEqual(response.status_code, 200)
        form = response.context["form"]

        self.assertEqual(
            form.errors["__all__"][0],
            "Cannot assign to section 'Transport', it does not exist.",
        )

        self.assertEqual(Assigned.objects.count(), 5)

    def test_assignments_already_made_error(self):
        u = User.objects.create(
            username="test_marker@example.org", email="test_marker@example.org"
        )
        ms = MarkingSession.objects.get(label="Default")
        Assigned.objects.create(
            section=Section.objects.get(title="Transport", marking_session=ms),
            response_type=ResponseType.objects.get(type="First Mark"),
            marking_session=ms,
            user=u,
        )

        url = reverse("bulk_assign_volunteer")
        response = self.client.get(url)

        self.assertEqual(Assigned.objects.count(), 6)

        volunteer_file = (
            pathlib.Path(__file__).parent.resolve() / "data" / "test_volunteers.xlsx"
        )
        with open(volunteer_file, "rb") as fp:
            response = self.client.post(
                url,
                data={
                    "volunteer_list": fp,
                    "response_type": "First Mark",
                    "session": "Default",
                    "num_assignments": 1,
                },
            )

        self.assertEqual(response.status_code, 200)
        form = response.context["form"]

        self.assertEqual(
            form.errors["__all__"][0],
            "No assignments will be made, all volunteers must already have assignments.",
        )

        self.assertEqual(Assigned.objects.count(), 6)
