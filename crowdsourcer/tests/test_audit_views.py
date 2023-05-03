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
        u = User.objects.get(username="auditor")
        self.client.force_login(u)
        self.user = u


class TestSaveView(BaseTestCase):
    fixtures = [
        "authorities.json",
        "basics.json",
        "users.json",
        "questions.json",
        "options.json",
        "assignments.json",
        "responses.json",
        "council_responses.json",
    ]

    def test_save(self):
        url = reverse("authority_audit", args=("Aberdeenshire Council", "Transport"))
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
                "form-0-evidence": "this is evidence",
                "form-0-option": "14",
                "form-0-page_number": "1",
                "form-0-private_notes": "this is private notes",
                "form-0-public_notes": "public notes",
                "form-0-question": "281",
                "form-1-authority": 2,
                "form-1-evidence": "this is more evidence",
                "form-1-multi_option": ["162"],
                "form-1-page_number": "2",
                "form-1-private_notes": "this is more private notes",
                "form-1-public_notes": "more public notes",
                "form-1-question": "282",
            },
        )

        self.assertEqual(response.status_code, 200)
        msg = response.context.get("message", "")
        self.assertEquals(msg, "Your answers have been saved.")

        answers = Response.objects.filter(
            authority__name="Aberdeenshire Council",
            question__section__title="Transport",
            response_type__type="Audit",
        ).order_by("question__number")

        self.assertEquals(answers.count(), 2)

        self.assertEquals(answers[0].option.description, "Yes")
        self.assertEquals(answers[0].response_type.type, "Audit")
        self.assertEquals(answers[1].multi_option.first().description, "Bike share")
