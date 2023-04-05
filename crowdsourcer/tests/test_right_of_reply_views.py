from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from crowdsourcer.models import Assigned, PublicAuthority, Response


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
        self.assertEqual(
            response.url, "/authorities/Aberdeenshire%20Council/ror/sections/"
        )

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


class TestTwoCouncilsAssignmentView(BaseTestCase):
    def setUp(self):
        u = User.objects.get(username="council")
        self.client.force_login(u)
        self.user = u

        auth1 = u.marker.authority

        u.marker.authority = None
        u.marker.save()

        auth2 = PublicAuthority.objects.get(name="Aberdeen City Council")

        Assigned.objects.create(user=u, authority=auth1)
        Assigned.objects.create(user=u, authority=auth2)

    def test_homepage_redirect(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/authority_ror_authorities/")

    def test_council_homepage(self):
        url = reverse("authority_ror_authorities")
        response = self.client.get(url)

        context = response.context
        assignments = context["assignments"]

        self.assertEqual(len(assignments), 2)

        first = assignments[0]
        second = assignments[1]
        self.assertEqual(first.authority.name, "Aberdeen City Council")
        self.assertEqual(second.authority.name, "Aberdeenshire Council")

    def test_council_marking_page(self):
        url = reverse("authority_ror_sections", args=("Aberdeenshire Council",))
        response = self.client.get(url)

        context = response.context
        sections = context["sections"]

        self.assertEqual(len(sections), 7)


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
