import io

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

import pandas as pd

from crowdsourcer.models import (
    Assigned,
    Marker,
    MarkingSession,
    PublicAuthority,
    Response,
    ResponseType,
    Section,
)


class TestEmptyDB(TestCase):
    def test_home_page(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)


class TestHomePage(TestCase):
    fixtures = [
        "basics.json",
    ]

    def test_home_page(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)


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
        u = User.objects.get(username="marker")
        self.client.force_login(u)
        self.user = u


class TestSelectsCorrectMarkingSession(BaseTestCase):
    def setUp(self):
        u = User.objects.get(username="admin")
        self.client.force_login(u)
        self.user = u

        m = Marker.objects.create(
            user=u, response_type=ResponseType.objects.get(type="First Mark")
        )
        for ms in MarkingSession.objects.all():
            m.marking_session.add(ms)

    def test_uses_first_session(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)

        context = response.context
        self.assertEqual(context["marking_session"].label, "Default")

    def test_does_not_use_inactive_sessions(self):
        ms = MarkingSession.objects.get(label="Default")
        ms.active = False
        ms.save()

        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        context = response.context
        self.assertEqual(context["marking_session"].label, "Second Session")

    def test_uses_default_session_if_set(self):
        ms = MarkingSession.objects.get(label="Second Session")
        ms.default = True
        ms.save()

        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        context = response.context
        self.assertEqual(context["marking_session"].label, "Second Session")

        response = self.client.get("/Default/")
        self.assertEqual(response.status_code, 200)
        context = response.context
        self.assertEqual(context["marking_session"].label, "Default")

    def test_uses_marking_session_in_url(self):
        response = self.client.get("/Default/")
        self.assertEqual(response.status_code, 200)
        context = response.context
        self.assertEqual(context["marking_session"].label, "Default")

        response = self.client.get("/Second Session/")
        self.assertEqual(response.status_code, 200)
        context = response.context
        self.assertEqual(context["marking_session"].label, "Second Session")

    def test_uses_only_session_in_marker(self):
        m = Marker.objects.get(user=self.user)
        m.marking_session.set([MarkingSession.objects.get(label="Second Session")])

        response = self.client.get("/")
        self.assertRedirects(response, "/Second%20Session/")


class TestAssignmentView(BaseTestCase):
    fixtures = [
        "authorities.json",
        "basics.json",
        "users.json",
        "questions.json",
        "options.json",
        "assignments.json",
    ]

    def test_basics(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)

        context = response.context
        self.assertFalse(context["show_users"])

        progress = context["progress"]

        self.assertEqual(len(progress), 2)

        first = progress[0]
        second = progress[1]
        self.assertEqual(first["assignment"].section.title, "Buildings & Heating")
        self.assertEqual(second["assignment"].section.title, "Transport")

        self.assertEqual(first["total"], 1)
        self.assertEqual(first["complete"], 0)
        self.assertEqual(second["total"], 2)
        self.assertEqual(second["complete"], 0)

    def test_non_first_mark_assigned_user(self):
        rt = ResponseType.objects.get(type="Audit")
        u = User.objects.get(username="marker")
        m, _ = Marker.objects.get_or_create(user=u)
        m.response_type = rt
        m.save()

        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)

        context = response.context
        self.assertFalse(context["show_users"])

        progress = context["progress"]

        self.assertEqual(len(progress), 0)

        # have to delete to prevent a duplicate assignment
        Assigned.objects.filter(response_type=rt).delete()
        Assigned.objects.filter(user=u).update(response_type=rt)
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)

        context = response.context
        progress = context["progress"]
        self.assertEqual(len(progress), 2)

        first = progress[0]
        second = progress[1]
        self.assertEqual(first["assignment"].section.title, "Buildings & Heating")
        self.assertEqual(first["section_link"], "audit_section_authorities")
        self.assertEqual(second["assignment"].section.title, "Transport")
        self.assertEqual(second["section_link"], "audit_section_authorities")

    def test_assigned_other_marking_session(self):
        u = User.objects.get(username="other_marker")
        self.client.force_login(u)
        self.user = u

        response = self.client.get("/")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/Second%20Session/")
        response = self.client.get(response.url)
        context = response.context
        progress = context["progress"]
        self.assertEqual(len(progress), 1)
        first = progress[0]

        self.assertEqual(first["assignment"].section.title, "Transport")
        self.assertEqual(first["total"], 1)
        self.assertEqual(first["complete"], 0)

    def test_assigned_inactive_marking_session(self):
        u = User.objects.get(username="other_marker")
        self.client.force_login(u)
        self.user = u

        session = MarkingSession.objects.get(label="Second Session")
        session.active = False
        session.save()

        response = self.client.get("/")
        context = response.context
        progress = context["progress"]
        self.assertEqual(len(progress), 0)


class TestAssignmentCompletionStats(BaseTestCase):
    def test_completion_stats(self):
        response = self.client.get("/")
        context = response.context
        progress = context["progress"]

        first = progress[0]
        second = progress[1]
        self.assertEqual(first["complete"], 0)
        self.assertEqual(second["complete"], 1)

        Response.objects.create(
            authority_id=3,
            question_id=281,
            user=self.user,
            option_id=14,
            response_type_id=1,
            public_notes="public notrs",
            page_number="0",
            evidence="",
            private_notes="private notes",
        )

        Response.objects.create(
            authority_id=3,
            question_id=282,
            user=self.user,
            option_id=161,
            response_type_id=1,
            public_notes="public notrs",
            page_number="0",
            evidence="",
            private_notes="private notes",
        )

        response = self.client.get("/")
        context = response.context
        progress = context["progress"]

        second = progress[1]
        self.assertEqual(second["complete"], 2)

    def test_completion_stats_ignore_null_responses(self):
        response = self.client.get("/")
        context = response.context
        progress = context["progress"]

        second = progress[1]
        self.assertEqual(second["complete"], 1)

        Response.objects.filter(question_id=281, user=2).update(option=None)

        response = self.client.get("/")
        context = response.context
        progress = context["progress"]

        second = progress[1]
        self.assertEqual(second["complete"], 0)


class TestUserSectionProgressView(BaseTestCase):
    def test_view(self):
        url = reverse("section_authorities", args=("Transport",))
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        context = response.context
        self.assertEqual(len(context["authorities"]), 2)
        self.assertEqual(context["authorities"][0].num_responses, 2)
        self.assertEqual(context["authorities"][0].num_questions, 2)
        self.assertEqual(context["authorities"][1].num_responses, None)
        self.assertEqual(context["authorities"][1].num_questions, 2)

    def test_null_responses_ignored(self):
        Response.objects.filter(question_id=281, user=2).update(option=None)

        url = reverse("section_authorities", args=("Transport",))
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        context = response.context
        self.assertEqual(context["authorities"][0].num_responses, 1)


class TestSaveView(BaseTestCase):
    fixtures = [
        "authorities.json",
        "basics.json",
        "users.json",
        "questions.json",
        "options.json",
        "assignments.json",
    ]

    def test_no_access_unless_assigned(self):
        url = reverse(
            "authority_question_edit", args=("Aberdeenshire Council", "Biodiversity")
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)

        a = Assigned.objects.create(
            marking_session=MarkingSession.objects.get(label="Default"),
            user=self.user,
            section=Section.objects.get(title="Biodiversity"),
            authority=PublicAuthority.objects.get(name="Aberdeenshire Council"),
            response_type=ResponseType.objects.get(type="First Mark"),
        )

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        a.active = False
        a.save()

        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)

    def test_no_access_if_wrong_stage_assigned(self):
        url = reverse(
            "authority_question_edit", args=("Aberdeenshire Council", "Biodiversity")
        )

        Assigned.objects.create(
            marking_session=MarkingSession.objects.get(label="Default"),
            user=self.user,
            response_type=ResponseType.objects.get(type="Audit"),
            section=Section.objects.get(title="Biodiversity"),
            authority=PublicAuthority.objects.get(name="Aberdeenshire Council"),
        )

        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)

    def test_no_access_if_wrong_session(self):
        url = reverse(
            "authority_question_edit", args=("Aberdeenshire Council", "Biodiversity")
        )
        response = self.client.get(url)

        session = MarkingSession.objects.get(label="Second Session")

        a = Assigned.objects.create(
            marking_session=session,
            user=self.user,
            section=Section.objects.get(title="Biodiversity"),
            authority=PublicAuthority.objects.get(name="Aberdeenshire Council"),
            response_type=ResponseType.objects.get(type="First Mark"),
        )

        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)

        session = MarkingSession.objects.get(label="Default")
        a.marking_session = session
        a.save()

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_questions(self):
        url = reverse(
            "authority_question_edit", args=("Aberdeenshire Council", "Transport")
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        self.assertRegex(response.content, rb"vehicle fleet")
        self.assertNotRegex(response.content, rb"Second Session")

    def test_questions_alt_session(self):
        u = User.objects.get(username="other_marker")
        self.client.force_login(u)

        url = reverse(
            "session_urls:authority_question_edit",
            args=("Second Session", "Aberdeenshire Council", "Transport"),
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        self.assertRegex(response.content, rb"Second Session")
        self.assertNotRegex(response.content, rb"vehicle fleet")

    """
    @override_settings(
        FORM_LABELS={
            "Second Session": {
                "page_number": "We have overridden a label",
            }
        },
        FORM_HINTS={
            "Second Session": {
                "public_notes": "We have overridden a hint",
                "private_notes": "",
            }
        },
    )
    def test_label_override(self):
        u = User.objects.get(username="other_marker")
        self.client.force_login(u)

        url = reverse(
            "session_urls:authority_question_edit",
            args=("Second Session", "Aberdeenshire Council", "Transport"),
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        self.assertRegex(response.content, rb"overridden a label")
        self.assertRegex(response.content, rb"overridden a hint")
        self.assertNotRegex(response.content, rb"These will note be made public")
    """

    def test_save(self):
        url = reverse(
            "authority_question_edit", args=("Aberdeenshire Council", "Transport")
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        self.assertFalse(response.context["has_previous_questions"])

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

    @override_settings(
        MANDATORY_FIELDS={
            "Default": {
                "mandatory_if_response": ["public_notes", "evidence", "private_notes"],
                "mandatory_if_no": ["private_notes"],
            }
        }
    )
    def test_configurable_validation_all_questions(self):
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
        self.assertEquals(msg, "Your answers have been saved.")
        errors = response.context["form"].errors
        self.assertEquals(len(errors), 2)
        self.assertEquals(len(errors[0]), 0)
        self.assertEquals(len(errors[1]), 0)

        answers = Response.objects.filter(
            authority__name="Adur District Council",
            question__section__title="Transport",
        ).order_by("question__number")

        self.assertEquals(answers.count(), 1)

    @override_settings(
        MANDATORY_FIELDS={
            "Default": {
                "mandatory_if_response": [
                    "public_notes",
                    "page_number",
                    "evidence",
                    "private_notes",
                ],
                "mandatory_if_no": ["private_notes"],
                "1": {
                    "mandatory_if_response": [
                        "public_notes",
                        "evidence",
                        "private_notes",
                    ],
                    "mandatory_if_no": ["private_notes"],
                },
            }
        }
    )
    def test_configurable_validation_per_questions(self):
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
                "form-1-evidence": "foo",
                "form-1-multi_option": "161",
                "form-1-page_number": "",
                "form-1-private_notes": "qux",
                "form-1-public_notes": "bar",
            },
        )

        self.assertEqual(response.status_code, 200)
        msg = response.context.get("message", "")
        self.assertEquals(msg, "")
        errors = response.context["form"].errors
        self.assertEquals(len(errors), 2)
        self.assertEquals(len(errors[0]), 0)
        self.assertEquals(errors[1]["page_number"], ["This field is required"])

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

    # it's not possible with the django test client to do simultaneous form submissions
    # so this isn't testing that the bug is fixed, but it is testing that the fix doesn't
    # have any ill effects and that it exhibits the correct behaviour.
    #
    # see https://github.com/mysociety/ceuk-marking/issues/40
    def test_multi_save_fix(self):
        url = reverse(
            "authority_question_edit", args=("Aberdeenshire Council", "Transport")
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        answers = Response.objects.filter(
            authority__name="Aberdeenshire Council",
            question__section__title="Transport",
        ).order_by("question__number")

        self.assertEquals(answers.count(), 0)

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
        last_update = answers[1].last_update

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
        private_notes = answers[1].private_notes
        self.assertEquals(private_notes, "qux")

        # as the response was the same it should not have updated
        self.assertEquals(last_update, answers[1].last_update)

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
                "form-1-private_notes": "more qux",
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
        private_notes = answers[1].private_notes
        self.assertEquals(private_notes, "more qux")

        # as the response was different this should have updated
        self.assertNotEquals(last_update, answers[1].last_update)


class TestSaveWithPreviousQuestionsView(BaseTestCase):
    fixtures = [
        "authorities.json",
        "basics.json",
        "users.json",
        "questions.json",
        "options.json",
        "assignments.json",
    ]

    def test_save(self):
        u = User.objects.get(username="other_marker")
        self.client.force_login(u)

        url = reverse(
            "session_urls:authority_question_edit",
            args=("Second Session", "Aberdeenshire Council", "Transport"),
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        self.assertTrue(response.context["has_previous_questions"])


class TestAllAuthorityProgressView(BaseTestCase):
    def test_non_admin_denied(self):
        response = self.client.get(reverse("all_authority_progress"))
        self.assertEquals(response.status_code, 403)

    def test_view(self):
        u = User.objects.get(username="admin")
        self.client.force_login(u)

        response = self.client.get(reverse("all_authority_progress"))
        self.assertEquals(response.status_code, 200)
        context = response.context

        self.assertEquals(context["councils"]["complete"], 0)
        self.assertEquals(context["councils"]["total"], 4)


class TestAllSectionProgressView(BaseTestCase):
    def test_non_admin_denied(self):
        response = self.client.get(reverse("all_section_progress"))
        self.assertEquals(response.status_code, 403)

    def test_view(self):
        u = User.objects.get(username="admin")
        self.client.force_login(u)

        response = self.client.get(reverse("all_section_progress"))
        self.assertEquals(response.status_code, 200)
        context = response.context["progress"]

        self.assertEquals(context["Transport"]["complete"], 1)
        self.assertEquals(context["Transport"]["started"], 1)
        self.assertEquals(context["Transport"]["assigned"], 2)
        self.assertEquals(context["Transport"]["total"], 4)
        self.assertEquals(context["Buildings & Heating"]["started"], 1)
        self.assertEquals(context["Buildings & Heating"]["complete"], 0)
        self.assertEquals(context["Buildings & Heating"]["assigned"], 1)
        self.assertEquals(context["Buildings & Heating"]["total"], 4)

    def test_null_responses_ignored(self):
        Response.objects.filter(question_id=281, user=2).update(option=None)

        u = User.objects.get(username="admin")
        self.client.force_login(u)
        response = self.client.get(reverse("all_section_progress"))
        self.assertEqual(response.status_code, 200)

        context = response.context["progress"]
        self.assertEquals(context["Transport"]["complete"], 0)
        self.assertEquals(context["Transport"]["started"], 1)
        self.assertEquals(context["Transport"]["assigned"], 2)
        self.assertEquals(context["Transport"]["total"], 4)


class TestVolunteerProgressView(BaseTestCase):
    def test_non_admin_denied(self):
        response = self.client.get(reverse("volunteer_progress", args=(2,)))
        self.assertEquals(response.status_code, 403)

    def test_view(self):
        u = User.objects.get(username="admin")
        self.client.force_login(u)
        response = self.client.get(reverse("volunteer_progress", args=(2,)))
        self.assertEquals(response.status_code, 200)
        context = response.context["sections"]

        self.assertEquals(len(context), 2)
        b_and_h = context[0]
        tran = context[1]

        self.assertEqual(b_and_h["section"].title, "Buildings & Heating")
        self.assertEqual(b_and_h["totals"]["total"], 1)
        self.assertEqual(b_and_h["totals"]["complete"], 0)
        self.assertEqual(tran["section"].title, "Transport")
        self.assertEqual(tran["totals"]["total"], 2)
        self.assertEqual(tran["totals"]["complete"], 1)

    def test_view_other_session(self):
        u = User.objects.get(username="admin")
        self.client.force_login(u)
        response = self.client.get(
            reverse(
                "session_urls:volunteer_progress",
                args=(
                    "Second Session",
                    2,
                ),
            )
        )
        self.assertEquals(response.status_code, 200)
        context = response.context["sections"]

        self.assertEquals(len(context), 0)


class TestVolunteerProgressCSVView(BaseTestCase):
    def test_non_admin_denied(self):
        response = self.client.get(reverse("volunteer_csv_progress"))
        self.assertEquals(response.status_code, 403)

    def test_view(self):
        u = User.objects.get(username="admin")
        self.client.force_login(u)
        response = self.client.get(reverse("volunteer_csv_progress"))
        self.assertEquals(response.status_code, 200)

        content = response.content.decode("utf-8")
        df = pd.read_csv(io.StringIO(content))

        self.assertEquals(df.shape[0], 3)
        b_and_h = df.iloc[0]
        tran = df.iloc[1]
        tran_audit = df.iloc[2]

        self.assertEqual(b_and_h["username"], "marker")
        self.assertEqual(b_and_h["section"], "Buildings & Heating")
        self.assertEqual(b_and_h["stage"], "First Mark")
        self.assertEqual(b_and_h["councils_assigned"], 1)
        self.assertEqual(b_and_h["councils_completed"], 0)
        self.assertEqual(tran["username"], "marker")
        self.assertEqual(tran["section"], "Transport")
        self.assertEqual(tran["stage"], "First Mark")
        self.assertEqual(tran["councils_assigned"], 2)
        self.assertEqual(tran["councils_completed"], 1)
        self.assertEqual(tran_audit["username"], "auditor")
        self.assertEqual(tran_audit["section"], "Transport")
        self.assertEqual(tran_audit["stage"], "Audit")
        self.assertEqual(tran_audit["councils_assigned"], 1)
        self.assertEqual(tran_audit["councils_completed"], 0)

    def test_missing_section_in_assignment(self):
        a = Assigned.objects.get(
            user__username="marker",
            section__title="Transport",
            authority__name="Aberdeenshire Council",
        )
        a.section = None
        a.save()

        u = User.objects.get(username="admin")
        self.client.force_login(u)
        response = self.client.get(reverse("volunteer_csv_progress"))
        self.assertEquals(response.status_code, 200)

        content = response.content.decode("utf-8")
        df = pd.read_csv(io.StringIO(content))

        self.assertEquals(df.shape[0], 4)
        bad_section = df.iloc[2]

        self.assertEqual(bad_section["section"], "No section assigned")
        self.assertEqual(bad_section["councils_assigned"], 0)
        self.assertEqual(bad_section["councils_completed"], 0)

    def test_missing_response_type_in_assignment(self):
        a = Assigned.objects.get(
            user__username="marker",
            section__title="Transport",
            authority__name="Aberdeenshire Council",
        )
        a.response_type = None
        a.save()

        u = User.objects.get(username="admin")
        self.client.force_login(u)
        response = self.client.get(reverse("volunteer_csv_progress"))
        self.assertEquals(response.status_code, 200)

        content = response.content.decode("utf-8")
        df = pd.read_csv(io.StringIO(content))

        self.assertEquals(df.shape[0], 4)
        tran = df.iloc[1]
        tran_no_rt = df.iloc[2]

        self.assertEqual(tran["section"], "Transport")
        self.assertEqual(tran["stage"], "First Mark")
        self.assertEqual(tran["councils_assigned"], 1)
        self.assertEqual(tran["councils_completed"], 0)
        self.assertEqual(tran_no_rt["section"], "Transport")
        self.assertEqual(tran_no_rt["stage"], "No stage assigned")
        self.assertEqual(tran_no_rt["councils_assigned"], 1)
        self.assertEqual(tran_no_rt["councils_completed"], 0)
        a = Assigned.objects.get(
            user__username="marker",
            section__title="Transport",
            authority__name="Aberdeenshire Council",
        )


class TestAuthorityProgressView(BaseTestCase):
    def test_non_admin_denied(self):
        response = self.client.get(reverse("authority_progress", args=(2,)))
        self.assertEquals(response.status_code, 403)

    def test_view(self):
        u = User.objects.get(username="admin")
        self.client.force_login(u)

        response = self.client.get(
            reverse("authority_progress", args=("Aberdeen City Council",))
        )
        self.assertEquals(response.status_code, 200)
        context = response.context["sections"]

        self.assertEqual(len(context.keys()), 7)
        self.assertEquals(context["Buildings & Heating"]["responses"], 3)
        self.assertEquals(context["Buildings & Heating"]["total"], 7)
        self.assertEquals(context["Transport"]["responses"], 0)
        self.assertEquals(context["Transport"]["total"], 2)


class TestAuthorityLoginView(BaseTestCase):
    def test_view(self):
        u = User.objects.get(username="admin")
        self.client.force_login(u)

        response = self.client.get(reverse("authority_login_report"))
        self.assertEquals(response.status_code, 200)
        context = response.context["authorities"]

        self.assertEquals(len(context), 4)
        for auth in context:
            self.assertEquals(auth.has_logged_in, None)
            self.assertEquals(auth.multi_has_logged_in, None)

    def test_has_logged_in(self):
        u = User.objects.get(username="council")
        self.client.force_login(u)
        last_login = u.last_login

        u = User.objects.get(username="admin")
        self.client.force_login(u)

        response = self.client.get(reverse("authority_login_report"))
        self.assertEquals(response.status_code, 200)
        context = response.context["authorities"]

        for auth in context:
            if auth.name == "Aberdeenshire Council":
                self.assertEquals(auth.has_logged_in, last_login)
                self.assertEquals(auth.multi_has_logged_in, None)
            else:
                self.assertEquals(auth.has_logged_in, None)
                self.assertEquals(auth.multi_has_logged_in, None)

    def test_multi_auth_right_of_reply(self):
        u = User.objects.get(username="council")
        marker = u.marker
        a1 = marker.authority
        marker.authority = None
        marker.save()

        Assigned.objects.create(
            marking_session=MarkingSession.objects.get(label="Default"),
            user=u,
            authority=a1,
        )

        a2 = PublicAuthority.objects.get(name="Aberdeen City Council")
        Assigned.objects.create(
            marking_session=MarkingSession.objects.get(label="Default"),
            user=u,
            authority=a2,
        )

        self.client.force_login(u)
        last_login = u.last_login

        u = User.objects.get(username="admin")
        self.client.force_login(u)

        response = self.client.get(reverse("authority_login_report"))
        self.assertEquals(response.status_code, 200)
        context = response.context["authorities"]

        for auth in context:
            if (
                auth.name == "Aberdeenshire Council"
                or auth.name == "Aberdeen City Council"
            ):
                self.assertEquals(auth.has_logged_in, None)
                self.assertEquals(auth.multi_has_logged_in, last_login)
            else:
                self.assertEquals(auth.has_logged_in, None)
                self.assertEquals(auth.multi_has_logged_in, None)
