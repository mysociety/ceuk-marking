from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from crowdsourcer.models import Response


class BaseTestCase(TestCase):
    fixtures = [
        "authorities.json",
        "basics.json",
        "users.json",
        "questions.json",
        "options.json",
        "assignments.json",
        "responses.json",
        "ror_responses.json",
    ]

    def setUp(self):
        u = User.objects.get(username="council")
        self.client.force_login(u)
        self.user = u


class TestAssignmentView(BaseTestCase):
    def test_homepage_redirect(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 302)

    def test_council_homepage(self):
        url = reverse("authority_ror_sections", args=("Aberdeenshire Council",))
        response = self.client.get(url)

        context = response.context
        sections = context["sections"]

        self.assertEqual(len(sections), 7)

        first = sections[0]
        second = sections[1]
        self.assertEqual(first.title, "Buildings & Heating")
        self.assertEqual(second.title, "Transport")

        self.assertEqual(first.total, 7)
        self.assertEqual(first.complete, 2)
        self.assertEqual(second.total, 2)
        self.assertEqual(second.complete, 0)


class TestSaveView(BaseTestCase):
    fixtures = [
        "authorities.json",
        "basics.json",
        "users.json",
        "questions.json",
        "options.json",
        "assignments.json",
        "responses.json",
    ]

    def test_no_access_unless_from_council(self):
        url = reverse("authority_ror", args=("Aberdeen City Council", "Transport"))
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)

        url = reverse("authority_ror", args=("Aberdeenshire Council", "Transport"))

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_save(self):
        url = reverse("authority_ror", args=("Aberdeenshire Council", "Transport"))
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        response = self.client.post(
            url,
            data={
                "form-INITIAL_FORMS": 2,
                "form-MAX_NUM_FORMS": 2,
                "form-MIN_NUM_FORMS": 2,
                "form-TOTAL_FORMS": 2,
                "form-0-authority": 2,
                "form-0-private_notes": "",
                "form-0-agree_with_response": True,
                "form-0-question": "281",
                "form-1-authority": 2,
                "form-1-evidence": "this is evidence",
                "form-1-private_notes": "I do not agree",
                "form-1-agree_with_response": False,
                "form-1-question": "282",
            },
        )

        self.assertEqual(response.status_code, 200)
        msg = response.context.get("message", "")
        self.assertEquals(msg, "Your answers have been saved.")

        answers = Response.objects.filter(
            authority__name="Aberdeenshire Council",
            question__section__title="Transport",
            response_type__type="Right of Reply",
        ).order_by("question__number")

        self.assertEquals(answers.count(), 2)

        self.assertTrue(answers[0].agree_with_response)
