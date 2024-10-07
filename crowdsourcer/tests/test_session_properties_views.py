from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from crowdsourcer.models import (
    Marker,
    MarkingSession,
    PublicAuthority,
    ResponseType,
    SessionProperties,
    SessionPropertyValues,
)


class BaseTestCase(TestCase):
    fixtures = [
        "authorities.json",
        "basics.json",
        "users.json",
        "assignments.json",
        "session_properties.json",
    ]

    def setUp(self):
        u = User.objects.get(username="council")
        self.client.force_login(u)
        self.user = u


class TestLinkDisplayed(BaseTestCase):
    fixtures = [
        "authorities.json",
        "basics.json",
        "users.json",
        "assignments.json",
    ]

    def test_ror_link_displayed(self):
        url = reverse("authority_ror_sections", args=("Aberdeenshire Council",))
        response = self.client.get(url)

        context = response.context
        self.assertFalse(context["has_properties"])

        SessionProperties.objects.create(
            marking_session=MarkingSession.objects.get(label="Default"),
            stage=ResponseType.objects.get(type="Right of Reply"),
            property_type="text",
            name="a_property",
            label="A Property",
        )

        response = self.client.get(url)

        context = response.context
        self.assertTrue(context["has_properties"])


class TestPropertyFormPermissions(BaseTestCase):
    def test_404(self):
        url = reverse(
            "authority_properties",
            args=(
                "Aberdeenshire Council",
                "Bad Type",
            ),
        )

        response = self.client.get(url)
        self.assertEquals(404, response.status_code)

        url = reverse(
            "authority_properties",
            args=(
                "Fakeshire Council",
                "First Mark",
            ),
        )

    def test_stage_permissions(self):
        self.client.logout()

        url = reverse(
            "authority_properties",
            args=(
                "Aberdeenshire Council",
                "First Mark",
            ),
        )

        response = self.client.get(url)
        self.assertEquals(403, response.status_code)

        for username in ["council", "auditor", "other_marker"]:
            u = User.objects.get(username=username)
            self.client.force_login(u)
            response = self.client.get(url)
            self.assertEquals(403, response.status_code)

        for username in ["admin", "marker"]:
            u = User.objects.get(username=username)
            self.client.force_login(u)
            response = self.client.get(url)
            self.assertEquals(200, response.status_code)

    def test_right_of_reply_permissions(self):
        self.client.logout()

        url = reverse(
            "authority_properties",
            args=(
                "Aberdeenshire Council",
                "Right of Reply",
            ),
        )

        response = self.client.get(url)
        self.assertEquals(403, response.status_code)

        u = User.objects.get(username="marker")
        self.client.force_login(u)
        response = self.client.get(url)
        self.assertEquals(403, response.status_code)

        u = User.objects.get(username="admin")
        self.client.force_login(u)
        response = self.client.get(url)
        self.assertEquals(200, response.status_code)

        u = User.objects.create(username="other_council", is_active=True)
        m = Marker.objects.create(
            user=u,
            response_type=ResponseType.objects.get(type="Right of Reply"),
            authority=PublicAuthority.objects.get(name="Aberdeen City Council"),
        )
        m.marking_session.set([MarkingSession.objects.get(label="Default")])
        self.client.force_login(u)
        response = self.client.get(url)
        self.assertEquals(403, response.status_code)

    def test_properties_not_found(self):
        url = reverse(
            "authority_properties",
            args=(
                "Aberdeenshire Council",
                "Audit",
            ),
        )

        u = User.objects.get(username="admin")
        self.client.force_login(u)
        response = self.client.get(url)
        self.assertEquals(404, response.status_code)

        url = reverse(
            "authority_properties",
            args=(
                "Aberdeenshire Council",
                "First Mark",
            ),
        )
        url = f"/Second%20Session{url}"
        response = self.client.get(url)
        self.assertEquals(404, response.status_code)


class TestPropertyForm(BaseTestCase):
    def test_form(self):
        url = reverse(
            "authority_properties",
            args=(
                "Aberdeenshire Council",
                "Right of Reply",
            ),
        )

        properties = SessionPropertyValues.objects.filter(
            property__marking_session__label="Default",
            authority__name="Aberdeenshire Council",
            property__stage__type="Right of Reply",
        )

        response = self.client.get(url)
        self.assertEquals(200, response.status_code)

        self.assertEquals(0, properties.count())

        response = self.client.post(url, data={"ror_property": "Property Data"})

        self.assertEqual(response.status_code, 200)
        msg = response.context.get("message", "")
        self.assertEquals(msg, "Your answers have been saved.")

        self.assertEquals(1, properties.count())

        p = properties.first()
        self.assertEquals(p.property.name, "ror_property")
        self.assertEquals(p.value, "Property Data")
