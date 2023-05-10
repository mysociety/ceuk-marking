from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from crowdsourcer.models import Assigned, Response, ResponseType


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

        rt = ResponseType.objects.get(type="Audit")
        rt.active = True
        rt.save()


class TestAssignmentView(BaseTestCase):
    fixtures = [
        "authorities.json",
        "basics.json",
        "users.json",
        "questions.json",
        "options.json",
        "audit_assignments.json",
    ]

    def test_basics(self):
        u = User.objects.get(username="marker")
        self.client.force_login(u)
        self.user = u

        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)

        context = response.context
        self.assertFalse(context["show_users"])

        progress = context["progress"]

        self.assertEqual(len(progress), 2)

        first = progress[0]
        second = progress[1]
        self.assertEqual(first["assignment"].section.title, "Planning & Land Use")
        self.assertEqual(second["assignment"].section.title, "Governance & Finance")

        self.assertEqual(first["total"], 2)
        self.assertEqual(first["complete"], 0)
        self.assertEqual(second["total"], 1)
        self.assertEqual(second["complete"], 0)


class TestSaveView(BaseTestCase):
    fixtures = [
        "authorities.json",
        "basics.json",
        "users.json",
        "questions.json",
        "options.json",
        "assignments.json",
        "responses.json",
        "ror_responses.json",
        "council_responses.json",
        "audit_extra_council_responses.json",
    ]

    def test_permissions(self):
        u = User.objects.get(username="marker")
        self.client.force_login(u)

        url = reverse("authority_audit", args=("Aberdeenshire Council", "Transport"))
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)

        u = User.objects.get(username="auditor")
        self.client.force_login(u)

        url = reverse("authority_audit", args=("Aberdeenshire Council", "Transport"))
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        assignment = Assigned.objects.get(user=u)
        assignment.authority_id = 3
        assignment.save()

        url = reverse("authority_audit", args=("Aberdeenshire Council", "Transport"))
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)

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


class TestAllAuthorityProgressView(BaseTestCase):
    fixtures = [
        "authorities.json",
        "basics.json",
        "users.json",
        "questions.json",
        "options.json",
        "assignments.json",
        "responses.json",
        "ror_responses.json",
        "audit_responses.json",
    ]

    def test_non_admin_denied(self):
        response = self.client.get(reverse("audit_all_authority_progress"))
        self.assertEquals(response.status_code, 403)

    def test_view(self):
        u = User.objects.get(username="admin")
        self.client.force_login(u)

        response = self.client.get(reverse("audit_all_authority_progress"))
        self.assertEquals(response.status_code, 200)
        context = response.context

        self.assertEquals(context["councils"]["complete"], 0)
        self.assertEquals(context["councils"]["total"], 4)


class TestSectionProgressView(BaseTestCase):
    fixtures = [
        "authorities.json",
        "basics.json",
        "users.json",
        "questions.json",
        "options.json",
        "assignments.json",
        "responses.json",
        "ror_responses.json",
        "audit_responses.json",
    ]

    def test_non_admin_denied(self):
        response = self.client.get(reverse("audit_all_section_progress"))
        self.assertEquals(response.status_code, 403)

    def test_view(self):
        u = User.objects.get(username="admin")
        self.client.force_login(u)

        response = self.client.get(reverse("audit_all_section_progress"))
        self.assertEquals(response.status_code, 200)
        context = response.context["progress"]

        self.assertEquals(context["Transport"]["complete"], 1)
        self.assertEquals(context["Transport"]["started"], 2)
        self.assertEquals(context["Transport"]["assigned"], 1)
        self.assertEquals(context["Transport"]["total"], 4)
        self.assertEquals(context["Buildings & Heating"]["started"], 1)
        self.assertEquals(context["Buildings & Heating"]["complete"], 0)
        self.assertEquals(context["Buildings & Heating"]["assigned"], None)
        self.assertEquals(context["Buildings & Heating"]["total"], 4)
