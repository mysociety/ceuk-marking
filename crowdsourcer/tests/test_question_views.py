import pathlib

from django.contrib.auth.models import Permission, User
from django.test import TestCase
from django.urls import reverse

from crowdsourcer.models import Question, Response


class BaseTestCase(TestCase):
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
        p = Permission.objects.get(codename="can_manage_users")
        u = User.objects.get(username="volunteer_admin")
        u.user_permissions.add(p)

        self.client.force_login(u)
        self.user = u


class TestBulkUpload(BaseTestCase):
    def test_one_update_one_new(self):
        url = reverse("question_bulk_update", args=("Transport", "1"))
        response = self.client.get(url)

        q = Question.objects.get(
            section__title="Transport",
            section__marking_session__label="Default",
            number=1,
        )

        all_r = Response.objects.filter(question=q, response_type__type="First Mark")
        self.assertEqual(all_r.count(), 1)

        r = Response.objects.get(question=q, authority__name="Aberdeenshire Council")

        self.assertEqual(r.option.description, "Yes")
        self.assertEqual(r.page_number, "0")

        upload_file = (
            pathlib.Path(__file__).parent.resolve()
            / "data"
            / "test_question_upload.csv"
        )

        with open(upload_file, "rb") as fp:
            response = self.client.post(
                url,
                data={
                    "question": 281,
                    "updated_responses": fp,
                    "stage": "First Mark",
                },
            )

        self.assertRedirects(response, "/Default" + url)
        self.assertEqual(all_r.count(), 2)

        r = Response.objects.get(question=q, authority__name="Aberdeen City Council")

        self.assertEqual(r.option.description, "Yes")
        self.assertEqual(r.page_number, "99")

        r = Response.objects.get(question=q, authority__name="Aberdeenshire Council")

        self.assertEqual(r.option.description, "No")
        self.assertEqual(r.page_number, None)

    def test_one_new_one_unchanged(self):
        url = reverse("question_bulk_update", args=("Transport", "1"))
        response = self.client.get(url)

        q = Question.objects.get(
            section__title="Transport",
            section__marking_session__label="Default",
            number=1,
        )

        all_r = Response.objects.filter(question=q, response_type__type="First Mark")
        self.assertEqual(all_r.count(), 1)

        r = Response.objects.get(question=q, authority__name="Aberdeenshire Council")

        last_update = r.last_update
        self.assertEqual(r.option.description, "Yes")
        self.assertEqual(r.page_number, "0")

        upload_file = (
            pathlib.Path(__file__).parent.resolve()
            / "data"
            / "test_question_upload_one_unchanged.csv"
        )

        with open(upload_file, "rb") as fp:
            response = self.client.post(
                url,
                data={
                    "question": 281,
                    "updated_responses": fp,
                    "stage": "First Mark",
                },
            )

        self.assertRedirects(response, "/Default" + url)
        self.assertEqual(all_r.count(), 2)

        r = Response.objects.get(question=q, authority__name="Aberdeen City Council")

        self.assertEqual(r.option.description, "Yes")
        self.assertEqual(r.page_number, "99")

        r = Response.objects.get(question=q, authority__name="Aberdeenshire Council")

        self.assertEqual(r.option.description, "Yes")
        self.assertEqual(r.page_number, "0")
        self.assertEqual(last_update, r.last_update)
