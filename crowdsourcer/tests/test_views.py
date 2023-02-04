from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from crowdsourcer.models import Assigned, PublicAuthority, Response, Section


class TestHomePage(TestCase):
    def test_home_page(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)


class TestSaveView(TestCase):
    fixtures = [
        "authorities.json",
        "basics.json",
        "users.json",
        "questions.json",
        "options.json",
        "assignments.json",
    ]

    def setUp(self):
        u = User.objects.get(username="marker")
        self.client.force_login(u)
        self.user = u

    def test_no_access_unless_assigned(self):
        url = reverse(
            "authority_question_edit", args=("Aberdeenshire Council", "Biodiversity")
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)

        Assigned.objects.create(
            user=self.user,
            section=Section.objects.get(title="Biodiversity"),
            authority=PublicAuthority.objects.get(name="Aberdeenshire Council"),
        )

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_save(self):
        url = reverse(
            "authority_question_edit", args=("Aberdeenshire Council", "Transport")
        )
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
                "form-0-evidence": "foo",
                "form-0-option": "14",
                "form-0-page_number": "1",
                "form-0-private_notes": "qux",
                "form-0-public_notes": "bar",
                "form-0-question": "281",
                "form-1-authority": 2,
                "form-1-evidence": "foo",
                "form-1-multi_option": "161",
                "form-1-page_number": "1",
                "form-1-private_notes": "qux",
                "form-1-public_notes": "bar",
                "form-1-question": "282",
            },
        )

        self.assertEqual(response.status_code, 200)
        msg = response.context.get("message", "")
        self.assertEquals(msg, "Your answers have been saved.")

        answers = Response.objects.filter(
            authority__name="Aberdeenshire Council",
            question__section__title="Transport",
        ).order_by("question__number")

        self.assertEquals(answers.count(), 2)

        self.assertEquals(answers[0].option.description, "Yes")

        options = answers[1].multi_option
        self.assertEquals(options.count(), 1)
        self.assertEquals(options.first().description, "Car share")

    def test_partial_save(self):
        url = reverse(
            "authority_question_edit", args=("Adur District Council", "Transport")
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        response = self.client.post(
            url,
            data={
                "form-INITIAL_FORMS": 2,
                "form-MAX_NUM_FORMS": 2,
                "form-MIN_NUM_FORMS": 2,
                "form-TOTAL_FORMS": 2,
                "form-0-authority": 3,
                "form-0-evidence": "foo",
                "form-0-option": "14",
                "form-0-page_number": "1",
                "form-0-private_notes": "qux",
                "form-0-public_notes": "bar",
                "form-0-question": "281",
                "form-1-authority": 3,
                "form-1-question": "282",
            },
        )

        self.assertEqual(response.status_code, 200)
        msg = response.context.get("message", "")
        self.assertEquals(msg, "Your answers have been saved.")

        answers = Response.objects.filter(
            authority__name="Adur District Council",
            question__section__title="Transport",
        ).order_by("question__number")

        self.assertEquals(answers.count(), 1)

    def test_failed_validation(self):
        url = reverse(
            "authority_question_edit", args=("Adur District Council", "Transport")
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        response = self.client.post(
            url,
            data={
                "form-INITIAL_FORMS": 2,
                "form-MAX_NUM_FORMS": 2,
                "form-MIN_NUM_FORMS": 2,
                "form-TOTAL_FORMS": 2,
                "form-0-authority": 3,
                "form-0-evidence": "foo",
                "form-0-option": "14",
                "form-0-page_number": "",
                "form-0-private_notes": "qux",
                "form-0-public_notes": "bar",
                "form-0-question": "281",
                "form-1-authority": 3,
                "form-1-question": "282",
            },
        )

        self.assertEqual(response.status_code, 200)
        msg = response.context.get("message", "")
        self.assertEquals(msg, "")
        errors = response.context["form"].errors
        self.assertEquals(errors[0]["page_number"], ["This field is required"])

        answers = Response.objects.filter(
            authority__name="Adur District Council",
            question__section__title="Transport",
        ).order_by("question__number")

        self.assertEquals(answers.count(), 0)

    def test_missed_answer(self):
        url = reverse(
            "authority_question_edit", args=("Adur District Council", "Transport")
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        response = self.client.post(
            url,
            data={
                "form-INITIAL_FORMS": 2,
                "form-MAX_NUM_FORMS": 2,
                "form-MIN_NUM_FORMS": 2,
                "form-TOTAL_FORMS": 2,
                "form-0-authority": 3,
                "form-0-evidence": "foo",
                "form-0-option": "",
                "form-0-page_number": "",
                "form-0-private_notes": "qux",
                "form-0-public_notes": "bar",
                "form-0-question": "281",
                "form-1-authority": 3,
                "form-1-question": "282",
            },
        )

        self.assertEqual(response.status_code, 200)
        msg = response.context.get("message", "")
        self.assertEquals(msg, "")
        errors = response.context["form"].errors
        self.assertEquals(errors[0]["option"], ["This field is required"])

        answers = Response.objects.filter(
            authority__name="Adur District Council",
            question__section__title="Transport",
        ).order_by("question__number")

        self.assertEquals(answers.count(), 0)

    def test_validate_no_evidence(self):
        url = reverse(
            "authority_question_edit", args=("Adur District Council", "Transport")
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        response = self.client.post(
            url,
            data={
                "form-INITIAL_FORMS": 2,
                "form-MAX_NUM_FORMS": 2,
                "form-MIN_NUM_FORMS": 2,
                "form-TOTAL_FORMS": 2,
                "form-0-authority": 3,
                "form-0-evidence": "",
                "form-0-option": "15",
                "form-0-page_number": "",
                "form-0-private_notes": "qux",
                "form-0-public_notes": "",
                "form-0-question": "281",
                "form-1-authority": 3,
                "form-1-question": "282",
            },
        )

        self.assertEqual(response.status_code, 200)
        msg = response.context.get("message", "")
        self.assertEquals(msg, "Your answers have been saved.")

        answers = Response.objects.filter(
            authority__name="Adur District Council",
            question__section__title="Transport",
        ).order_by("question__number")

        self.assertEquals(answers.count(), 1)

    def test_partial_answers_skip_middle(self):
        url = reverse(
            "authority_question_edit",
            args=("Aberdeen City Council", "Buildings & Heating"),
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        response = self.client.post(
            url,
            data={
                "form-INITIAL_FORMS": 7,
                "form-MAX_NUM_FORMS": 7,
                "form-MIN_NUM_FORMS": 7,
                "form-TOTAL_FORMS": 7,
                "form-0-authority": "1",
                "form-0-evidence": "",
                "form-0-option": "1",
                "form-0-page_number": "",
                "form-0-private_notes": "private notes q 269",
                "form-0-public_notes": "",
                "form-0-question": "269",
                "form-1-authority": "1",
                "form-1-evidence": "",
                "form-1-option": "",
                "form-1-page_number": "",
                "form-1-private_notes": "",
                "form-1-public_notes": "",
                "form-1-question": "272",
                "form-2-authority": "1",
                "form-2-evidence": "",
                "form-2-option": "",
                "form-2-page_number": "",
                "form-2-private_notes": "",
                "form-2-public_notes": "",
                "form-2-question": "273",
                "form-3-authority": "1",
                "form-3-evidence": "evidence link 277",
                "form-3-option": "9",
                "form-3-page_number": "277",
                "form-3-private_notes": "private notes q 277",
                "form-3-public_notes": "public notes q 277",
                "form-3-question": "277",
                "form-4-authority": "1",
                "form-4-evidence": "",
                "form-4-option": "",
                "form-4-page_number": "",
                "form-4-private_notes": "",
                "form-4-public_notes": "",
                "form-4-question": "278",
                "form-5-authority": "1",
                "form-5-evidence": "",
                "form-5-option": "",
                "form-5-page_number": "",
                "form-5-private_notes": "",
                "form-5-public_notes": "",
                "form-5-question": "279",
                "form-6-authority": "1",
                "form-6-evidence": "",
                "form-6-option": "",
                "form-6-page_number": "",
                "form-6-private_notes": "",
                "form-6-public_notes": "",
                "form-6-question": "280",
            },
        )

        self.assertEqual(response.status_code, 200)
        msg = response.context.get("message", "")
        self.assertEquals(msg, "Your answers have been saved.")

        answers = Response.objects.filter(
            authority__name="Aberdeen City Council",
            question__section__title="Buildings & Heating",
        ).order_by("question__number")

        self.assertEquals(answers.count(), 2)
