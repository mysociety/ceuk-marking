from django.test import TestCase

from crowdsourcer.models import Response


class TestEvidenceLinks(TestCase):
    cases = [
        {
            "in": "this is a link: http://example.com/ to evidence",
            "out": [
                "http://example.com/",
            ],
        },
        {
            "in": "this is a two link: http://example.com/ and http://example.org/path to evidence",
            "out": [
                "http://example.com/",
                "http://example.org/path",
            ],
        },
        {
            "in": "this is a two link: https://example.com/ and http://example.org/path to evidence",
            "out": [
                "https://example.com/",
                "http://example.org/path",
            ],
        },
        {
            "in": "this is a no http link: www.example.com/ and http://example.org/path to evidence",
            "out": [
                "www.example.com/",
                "http://example.org/path",
            ],
        },
        {
            "in": "this has no links",
            "out": [],
        },
        {
            "in": "this has no links but does have a www",
            "out": [],
        },
        {
            "in": "",
            "out": [],
        },
        {
            "in": None,
            "out": [],
        },
    ]

    def test_home_page(self):
        for case in self.cases:
            r = Response(public_notes=case["in"])

            self.assertEquals(r.evidence_links, case["out"])
