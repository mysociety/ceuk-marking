import io

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

import pandas as pd

from crowdsourcer.models import (
    Assigned,
    MarkingSession,
    PublicAuthority,
    Response,
    ResponseType,
    SessionProperties,
    SessionPropertyValues,
)


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
        "session_properties",
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
            response.url, "/Default/authorities/Aberdeenshire%20Council/ror/sections/"
        )

    def test_homepage_redirect_with_marking_session(self):
        self.user.marker.marking_session.clear()
        self.user.marker.marking_session.add(
            MarkingSession.objects.get(label="Second Session")
        )

        response = self.client.get("/")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.url,
            "/Second%20Session/authorities/Aberdeenshire%20Council/ror/sections/",
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

        self.assertEqual(first.total, 11)
        self.assertEqual(first.complete, 2)
        self.assertEqual(second.total, 2)
        self.assertEqual(second.complete, 0)

    def test_null_answers_ignored(self):
        Response.objects.filter(question_id=272, user=3, response_type=2).update(
            agree_with_response=None
        )
        url = reverse("authority_ror_sections", args=("Aberdeenshire Council",))
        response = self.client.get(url)

        context = response.context
        sections = context["sections"]

        self.assertEqual(len(sections), 7)

        first = sections[0]
        self.assertEqual(first.title, "Buildings & Heating")

        self.assertEqual(first.complete, 1)

    def test_duplicate_answers_ignored(self):
        Response.objects.filter(question_id=272, user=3, response_type=2).update(
            question_id=273
        )
        url = reverse("authority_ror_sections", args=("Aberdeenshire Council",))
        response = self.client.get(url)

        context = response.context
        sections = context["sections"]

        self.assertEqual(len(sections), 7)

        first = sections[0]
        self.assertEqual(first.title, "Buildings & Heating")

        self.assertEqual(first.complete, 1)


class TestTwoCouncilsAssignmentView(BaseTestCase):
    def setUp(self):
        u = User.objects.get(username="council")
        self.client.force_login(u)
        self.user = u

        auth1 = u.marker.authority

        u.marker.authority = None
        u.marker.save()

        auth2 = PublicAuthority.objects.get(name="Aberdeen City Council")
        rt = ResponseType.objects.get(type="Right of Reply")

        Assigned.objects.create(
            marking_session=MarkingSession.objects.get(label="Default"),
            user=u,
            authority=auth1,
            response_type=rt,
        )
        Assigned.objects.create(
            marking_session=MarkingSession.objects.get(label="Default"),
            user=u,
            authority=auth2,
            response_type=rt,
        )

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

    def test_council_section_list(self):
        url = reverse("authority_ror_sections", args=("Aberdeenshire Council",))
        response = self.client.get(url)

        context = response.context
        sections = context["sections"]

        self.assertEqual(len(sections), 7)

    def test_council_marking_page(self):
        url = reverse("authority_ror", args=("Aberdeenshire Council", "Transport"))
        response = self.client.get(url)

        context = response.context
        authority = context["authority"]

        self.assertEqual(authority.name, "Aberdeenshire Council")


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

    def test_no_access_if_wrong_stage_single_council(self):
        url = reverse("authority_ror", args=("Aberdeenshire Council", "Transport"))
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        rt = ResponseType.objects.get(type="Audit")
        m = self.user.marker
        m.response_type = rt
        m.save()

        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)

    def test_no_access_if_wrong_stage_multi_council(self):
        auth2 = PublicAuthority.objects.get(name="Aberdeen City Council")

        a = Assigned.objects.create(
            marking_session=MarkingSession.objects.get(label="Default"),
            response_type=ResponseType.objects.get(type="Right of Reply"),
            user=self.user,
            authority=auth2,
        )

        url = reverse("authority_ror", args=("Aberdeen City Council", "Transport"))
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        rt = ResponseType.objects.get(type="Audit")
        a.response_type = rt
        a.save()

        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)

    def test_no_access_if_wrong_marking_session_single_council(self):
        url = reverse("authority_ror", args=("Aberdeenshire Council", "Transport"))
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        session = MarkingSession.objects.get(label="Second Session")
        m = self.user.marker
        m.marking_session.clear()
        m.marking_session.add(session)

        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)

        session = MarkingSession.objects.get(label="Default")
        m.marking_session.clear()
        m.marking_session.add(session)

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_no_access_if_wrong_marking_session_multi_council(self):
        auth2 = PublicAuthority.objects.get(name="Aberdeen City Council")

        a = Assigned.objects.create(
            marking_session=MarkingSession.objects.get(label="Default"),
            response_type=ResponseType.objects.get(type="Right of Reply"),
            user=self.user,
            authority=auth2,
        )

        url = reverse("authority_ror", args=("Aberdeen City Council", "Transport"))
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        session = MarkingSession.objects.get(label="Second Session")
        a.marking_session = session
        a.save()

        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)

        session = MarkingSession.objects.get(label="Default")
        a.marking_session = session
        a.save()

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_display_option(self):
        response = Response.objects.get(
            authority_id=2,
            question_id=281,
            response_type_id=1,
        )
        option = response.option
        option.description = "Option Response"
        option.save()

        url = reverse("authority_ror", args=("Aberdeenshire Council", "Transport"))
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        form = response.context["form"]
        initial = form.forms[0].initial

        self.assertEquals(
            initial["original_response"].option.description, "Option Response"
        )
        self.assertEquals(
            list(initial["original_response"].multi_option.values("id")), []
        )

        content = response.content
        self.assertRegex(content, rb"<p>\s*Option Response\s*</p>")

    def test_display_multi_option(self):
        response = Response.objects.get(
            authority_id=2,
            question_id=281,
            response_type_id=1,
        )
        option = response.option
        option.description = "Multi Response"
        option.save()
        response.option = None
        response.multi_option.add(option)
        response.save()

        url = reverse("authority_ror", args=("Aberdeenshire Council", "Transport"))
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        form = response.context["form"]

        initial = form.forms[0].initial

        self.assertEquals(initial["original_response"].option, None)
        self.assertEquals(
            list(
                initial["original_response"].multi_option.values_list("id", flat=True)
            ),
            [option.id],
        )

        content = response.content
        self.assertRegex(content, rb"<p>[\n\s]*Multi Response,[\n\s]*</p>")

    def test_display_no_answer(self):
        response = Response.objects.get(
            authority_id=2,
            question_id=281,
            response_type_id=1,
        )
        response.delete()

        url = reverse("authority_ror", args=("Aberdeenshire Council", "Transport"))
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        form = response.context["form"]

        initial = form.forms[0].initial

        self.assertIsNone(initial.get("original_response", None))

        content = response.content
        self.assertRegex(content, rb"<div[^>]*>[\s\n]*<p>\(none\)</p>[\s\n]*</div>")

    def test_questions(self):
        url = reverse("authority_ror", args=("Aberdeenshire Council", "Transport"))
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        self.assertRegex(response.content, rb"vehicle fleet")
        self.assertNotRegex(response.content, rb"Second Session")

    def test_questions_alt_session(self):
        u = User.objects.get(username="other_marker")
        rt = ResponseType.objects.get(type="Right of Reply")

        Assigned.objects.filter(user=u).delete()

        u.marker.response_type = rt
        u.marker.authority = PublicAuthority.objects.get(name="Aberdeenshire Council")
        u.marker.save()

        self.client.force_login(u)

        url = reverse(
            "session_urls:authority_ror",
            args=("Second Session", "Aberdeenshire Council", "Transport"),
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        self.assertRegex(response.content, rb"Second Session")
        self.assertNotRegex(response.content, rb"vehicle fleet")

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

    def test_blank_existing_entry(self):
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

        first = answers.first()
        second = answers.last()
        self.assertEquals(first.agree_with_response, True)
        self.assertEquals(second.agree_with_response, False)
        self.assertEquals(second.private_notes, "I do not agree")

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
                "form-1-evidence": "",
                "form-1-private_notes": "",
                "form-1-agree_with_response": "",
                "form-1-question": "282",
            },
        )

        answers = Response.objects.filter(
            authority__name="Aberdeenshire Council",
            question__section__title="Transport",
            response_type__type="Right of Reply",
        ).order_by("question__number")

        first = answers.first()
        second = answers.last()
        self.assertEquals(first.agree_with_response, True)
        self.assertEquals(second.agree_with_response, None)
        self.assertEquals(second.private_notes, "")


class TestChallengeView(BaseTestCase):
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

    def test_permissions(self):
        url = reverse("section_ror_progress")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)

        u = User.objects.get(username="marker")
        self.client.force_login(u)

        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)

        u = User.objects.get(username="admin")
        self.client.force_login(u)

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_view(self):
        u = User.objects.get(username="admin")
        self.client.force_login(u)
        url = reverse("section_ror_progress")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        progress = response.context["progress"]

        self.assertEqual(len(progress.keys()), 7)

        tran = progress["Transport"]
        self.assertEqual(tran["total"], 4)
        self.assertEqual(tran["complete"], 0)
        self.assertEqual(tran["started"], 0)
        self.assertEqual(tran["challenges"], 0)

        b_and_h = progress["Buildings & Heating"]
        self.assertEqual(b_and_h["total"], 4)
        self.assertEqual(b_and_h["complete"], 0)
        self.assertEqual(b_and_h["started"], 1)
        self.assertEqual(b_and_h["challenges"], 1)

    def test_view_other_session(self):
        u = User.objects.get(username="admin")
        self.client.force_login(u)
        url = reverse("session_urls:section_ror_progress", args=("Second Session",))
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        progress = response.context["progress"]

        self.assertEqual(len(progress.keys()), 2)


class TestCSVDownloadView(BaseTestCase):
    def get_download_df(self):
        url = reverse("authority_ror_download", args=("Aberdeenshire Council",))
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        content = response.content.decode("utf-8")
        # the dtype bit stops pandas doing annoying conversions and ending up
        # with page numers as floats etc
        df = pd.read_csv(io.StringIO(content), dtype="object")
        # avoid nan results
        df = df.fillna("")

        return df

    def test_download(self):
        df = self.get_download_df()

        self.assertEqual(df.shape[0], 2)
        b_and_h_q4 = df.iloc[0]
        b_and_h_q5 = df.iloc[1]

        self.assertEqual(b_and_h_q4.question_no, "4")
        self.assertEqual(
            b_and_h_q4.first_mark_response,
            "The council has completed an exercise to measure how much, approximately, it will cost them to retrofit all homes (to EPC C or higher, or equivalent) and there is a target date of 2030.",
        )
        self.assertEqual(b_and_h_q4.agree_with_mark, "Yes")
        self.assertEqual(b_and_h_q4.council_evidence, "")

        self.assertEqual(b_and_h_q5.question_no, "5")
        self.assertEqual(
            b_and_h_q5.first_mark_response,
            "The council convenes or is a member of a local retrofit partnership",
        )
        self.assertEqual(b_and_h_q5.council_evidence, "We do not agree for reasons")
        self.assertEqual(b_and_h_q5.agree_with_mark, "No")
        self.assertEqual(b_and_h_q5.council_notes, "a council objection")

    def test_download_with_props(self):
        sp = SessionProperties.objects.get(name="ror_property")
        SessionPropertyValues.objects.create(
            property=sp,
            authority=PublicAuthority.objects.get(name="Aberdeenshire Council"),
            value="This is a property value",
        )

        df = self.get_download_df()
        self.assertEqual(df.shape[0], 3)
        prop = df.iloc[2]

        self.assertEqual(prop.section, "Additional information")
        self.assertEqual(prop.question, "Right of Reply Property")
        self.assertEqual(prop.council_notes, "This is a property value")
