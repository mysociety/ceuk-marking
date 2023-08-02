from io import StringIO
from unittest import mock

from django.core.management import call_command
from django.test import TestCase

from crowdsourcer.models import Question, Response
from crowdsourcer.scoring import get_section_maxes

max_section = {
    "Buildings & Heating": {
        "Single Tier": 28,
        "District": 27,
        "County": 28,
        "Northern Ireland": 12,
        "Combined Authority": 0,
    },
    "Transport": {
        "Single Tier": 7,
        "District": 7,
        "County": 7,
        "Northern Ireland": 7,
        "Combined Authority": 0,
    },
    "Planning & Land Use": {
        "Single Tier": 4,
        "District": 4,
        "County": 0,
        "Northern Ireland": 1,
        "Combined Authority": 0,
    },
    "Governance & Finance": {
        "Single Tier": 3,
        "District": 3,
        "County": 3,
        "Northern Ireland": 3,
        "Combined Authority": 0,
    },
    "Biodiversity": {
        "Single Tier": 1,
        "District": 1,
        "County": 1,
        "Northern Ireland": 1,
        "Combined Authority": 0,
    },
    "Collaboration & Engagement": {
        "Single Tier": 5,
        "District": 5,
        "County": 5,
        "Northern Ireland": 5,
        "Combined Authority": 0,
    },
    "Waste Reduction & Food": {
        "Single Tier": 5,
        "District": 5,
        "County": 5,
        "Northern Ireland": 5,
        "Combined Authority": 0,
    },
}
max_totals = {
    "Single Tier": 53,
    "District": 52,
    "County": 49,
    "Northern Ireland": 34,
    "Combined Authority": 0,
}

max_questions = {
    "Buildings & Heating": {"5": 1, "9": 1, "10": 1, "12": 1, "1": 5, "4": 16, "11": 3},
    "Transport": {"1": 1, "2": 6},
    "Planning & Land Use": {"1": 1, "2": 3},
    "Governance & Finance": {"1a": 1, "1b": 1, "2": 1},
    "Biodiversity": {"1": 1},
    "Collaboration & Engagement": {"1": 1, "2a": 1, "2b": 3},
    "Waste Reduction & Food": {"1": 1, "2": 1, "1b": 3},
}

max_weighted = {
    "Buildings & Heating": {
        "Single Tier": 12,
        "District": 10,
        "County": 12,
        "Northern Ireland": 9,
        "Combined Authority": 0,
    },
    "Transport": {
        "Single Tier": 2,
        "District": 2,
        "County": 2,
        "Northern Ireland": 2,
        "Combined Authority": 0,
    },
    "Planning & Land Use": {
        "Single Tier": 2,
        "District": 2,
        "County": 0,
        "Northern Ireland": 1,
        "Combined Authority": 0,
    },
    "Governance & Finance": {
        "Single Tier": 3,
        "District": 3,
        "County": 3,
        "Northern Ireland": 3,
        "Combined Authority": 0,
    },
    "Biodiversity": {
        "Single Tier": 1,
        "District": 1,
        "County": 1,
        "Northern Ireland": 1,
        "Combined Authority": 0,
    },
    "Collaboration & Engagement": {
        "Single Tier": 5,
        "District": 5,
        "County": 5,
        "Northern Ireland": 5,
        "Combined Authority": 0,
    },
    "Waste Reduction & Food": {
        "Single Tier": 3,
        "District": 3,
        "County": 3,
        "Northern Ireland": 3,
        "Combined Authority": 0,
    },
}


class BaseCommandTestCase(TestCase):
    def call_command(self, command, *args, **kwargs):
        out = StringIO()
        call_command(
            command,
            *args,
            stdout=out,
            stderr=StringIO(),
            **kwargs,
        )
        return out.getvalue()


class ExportNoMarksTestCase(BaseCommandTestCase):
    fixtures = [
        "authorities.json",
        "basics.json",
        "users.json",
        "questions.json",
        "options.json",
    ]

    def test_max_calculation(self):
        (
            section,
            totals,
            q_maxes,
            weighted,
        ) = get_section_maxes()

        self.assertEquals(section, max_section)
        self.assertEquals(totals, max_totals)
        self.assertEquals(q_maxes, max_questions)
        self.assertEquals(weighted, max_weighted)

    def test_max_calculation_with_unweighted_q(self):
        Question.objects.filter(pk=272).update(weighting="unweighted")

        (
            section,
            totals,
            q_maxes,
            weighted,
        ) = get_section_maxes()

        local_max_w = max_weighted.copy()
        local_max_w["Buildings & Heating"] = {
            "Single Tier": 27,
            "District": 25,
            "County": 27,
            "Northern Ireland": 9,
            "Combined Authority": 0,
        }

        self.assertEquals(section, max_section)
        self.assertEquals(totals, max_totals)
        self.assertEquals(q_maxes, max_questions)
        self.assertEquals(weighted, local_max_w)

    @mock.patch("crowdsourcer.management.commands.export_marks.Command.write_files")
    def test_export_with_no_marks(self, write_mock):
        self.call_command(
            "export_marks",
        )

        expected_percent = [
            {
                "council": "Aberdeen City Council",
                "gss": "S12000033",
                "Buildings & Heating": 0.0,
                "Transport": 0.0,
                "Planning & Land Use": 0.0,
                "Governance & Finance": 0.0,
                "Biodiversity": 0.0,
                "Collaboration & Engagement": 0.0,
                "Waste Reduction & Food": 0.0,
                "raw_total": 0.0,
                "weighted_total": 0.0,
            },
            {
                "council": "Aberdeenshire Council",
                "gss": "S12000034",
                "Buildings & Heating": 0.0,
                "Transport": 0.0,
                "Planning & Land Use": 0.0,
                "Governance & Finance": 0.0,
                "Biodiversity": 0.0,
                "Collaboration & Engagement": 0.0,
                "Waste Reduction & Food": 0.0,
                "raw_total": 0.0,
                "weighted_total": 0.0,
            },
            {
                "council": "Adur District Council",
                "gss": "E07000223",
                "Buildings & Heating": 0.0,
                "Transport": 0.0,
                "Planning & Land Use": 0.0,
                "Governance & Finance": 0.0,
                "Biodiversity": 0.0,
                "Collaboration & Engagement": 0.0,
                "Waste Reduction & Food": 0.0,
                "raw_total": 0.0,
                "weighted_total": 0.0,
            },
        ]

        expected_raw = [
            {
                "Buildings & Heating": 0,
                "Transport": 0,
                "Planning & Land Use": 0,
                "Governance & Finance": 0,
                "Biodiversity": 0,
                "Collaboration & Engagement": 0,
                "Waste Reduction & Food": 0,
                "council": "Aberdeen City Council",
                "gss": "S12000033",
                "total": 0,
            },
            {
                "Buildings & Heating": 0,
                "Transport": 0,
                "Planning & Land Use": 0,
                "Governance & Finance": 0,
                "Biodiversity": 0,
                "Collaboration & Engagement": 0,
                "Waste Reduction & Food": 0,
                "council": "Aberdeenshire Council",
                "gss": "S12000034",
                "total": 0,
            },
            {
                "Buildings & Heating": 0,
                "Transport": 0,
                "Planning & Land Use": 0,
                "Governance & Finance": 0,
                "Biodiversity": 0,
                "Collaboration & Engagement": 0,
                "Waste Reduction & Food": 0,
                "council": "Adur District Council",
                "gss": "E07000223",
                "total": 0,
            },
        ]

        expected_linear = [
            ("Aberdeen City Council", "S12000033", "Buildings & Heating", 0, 28),
            ("Aberdeen City Council", "S12000033", "Transport", 0, 7),
            ("Aberdeen City Council", "S12000033", "Planning & Land Use", 0, 4),
            ("Aberdeen City Council", "S12000033", "Governance & Finance", 0, 3),
            ("Aberdeen City Council", "S12000033", "Biodiversity", 0, 1),
            ("Aberdeen City Council", "S12000033", "Collaboration & Engagement", 0, 5),
            ("Aberdeen City Council", "S12000033", "Waste Reduction & Food", 0, 5),
            ("Aberdeenshire Council", "S12000034", "Buildings & Heating", 0, 28),
            ("Aberdeenshire Council", "S12000034", "Transport", 0, 7),
            ("Aberdeenshire Council", "S12000034", "Planning & Land Use", 0, 4),
            ("Aberdeenshire Council", "S12000034", "Governance & Finance", 0, 3),
            ("Aberdeenshire Council", "S12000034", "Biodiversity", 0, 1),
            ("Aberdeenshire Council", "S12000034", "Collaboration & Engagement", 0, 5),
            ("Aberdeenshire Council", "S12000034", "Waste Reduction & Food", 0, 5),
            ("Adur District Council", "E07000223", "Buildings & Heating", 0, 27),
            ("Adur District Council", "E07000223", "Transport", 0, 7),
            ("Adur District Council", "E07000223", "Planning & Land Use", 0, 4),
            ("Adur District Council", "E07000223", "Governance & Finance", 0, 3),
            ("Adur District Council", "E07000223", "Biodiversity", 0, 1),
            ("Adur District Council", "E07000223", "Collaboration & Engagement", 0, 5),
            ("Adur District Council", "E07000223", "Waste Reduction & Food", 0, 5),
        ]

        percent, raw, linear = write_mock.call_args[0]
        self.assertEquals(percent, expected_percent)
        self.assertEquals(raw, expected_raw)
        self.assertEquals(linear, expected_linear)


class ExportWithMarksTestCase(BaseCommandTestCase):
    fixtures = [
        "authorities.json",
        "basics.json",
        "users.json",
        "questions.json",
        "options.json",
        "audit_responses.json",
    ]

    expected_percent = [
        {
            "council": "Aberdeen City Council",
            "gss": "S12000033",
            "Buildings & Heating": 0.10714285714285714,
            "Transport": 0.0,
            "Planning & Land Use": 0.0,
            "Governance & Finance": 0.0,
            "Biodiversity": 0.0,
            "Collaboration & Engagement": 0.0,
            "Waste Reduction & Food": 0.0,
            "raw_total": 0.05660377358490566,
            "weighted_total": 0.021041666666666667,
        },
        {
            "council": "Aberdeenshire Council",
            "gss": "S12000034",
            "Buildings & Heating": 0.0,
            "Transport": 0.2857142857142857,
            "Planning & Land Use": 0.0,
            "Governance & Finance": 0.0,
            "Biodiversity": 0.0,
            "Collaboration & Engagement": 0.0,
            "Waste Reduction & Food": 0.0,
            "raw_total": 0.03773584905660377,
            "weighted_total": 0.11666666666666668,
        },
        {
            "council": "Adur District Council",
            "gss": "E07000223",
            "Buildings & Heating": 0.0,
            "Transport": 0.14285714285714285,
            "Planning & Land Use": 0.0,
            "Governance & Finance": 0.0,
            "Biodiversity": 0.0,
            "Collaboration & Engagement": 0.0,
            "Waste Reduction & Food": 0.0,
            "raw_total": 0.019230769230769232,
            "weighted_total": 0.004166666666666667,
        },
    ]

    expected_raw = [
        {
            "Buildings & Heating": 3,
            "Transport": 0,
            "Planning & Land Use": 0,
            "Governance & Finance": 0,
            "Biodiversity": 0,
            "Collaboration & Engagement": 0,
            "Waste Reduction & Food": 0,
            "council": "Aberdeen City Council",
            "gss": "S12000033",
            "total": 3,
        },
        {
            "Buildings & Heating": 0,
            "Transport": 2,
            "Planning & Land Use": 0,
            "Governance & Finance": 0,
            "Biodiversity": 0,
            "Collaboration & Engagement": 0,
            "Waste Reduction & Food": 0,
            "council": "Aberdeenshire Council",
            "gss": "S12000034",
            "total": 2,
        },
        {
            "Buildings & Heating": 0,
            "Transport": 1,
            "Planning & Land Use": 0,
            "Governance & Finance": 0,
            "Biodiversity": 0,
            "Collaboration & Engagement": 0,
            "Waste Reduction & Food": 0,
            "council": "Adur District Council",
            "gss": "E07000223",
            "total": 1,
        },
    ]

    expected_linear = [
        ("Aberdeen City Council", "S12000033", "Buildings & Heating", 3, 28),
        ("Aberdeen City Council", "S12000033", "Transport", 0, 7),
        ("Aberdeen City Council", "S12000033", "Planning & Land Use", 0, 4),
        ("Aberdeen City Council", "S12000033", "Governance & Finance", 0, 3),
        ("Aberdeen City Council", "S12000033", "Biodiversity", 0, 1),
        ("Aberdeen City Council", "S12000033", "Collaboration & Engagement", 0, 5),
        ("Aberdeen City Council", "S12000033", "Waste Reduction & Food", 0, 5),
        ("Aberdeenshire Council", "S12000034", "Buildings & Heating", 0, 28),
        ("Aberdeenshire Council", "S12000034", "Transport", 2, 7),
        ("Aberdeenshire Council", "S12000034", "Planning & Land Use", 0, 4),
        ("Aberdeenshire Council", "S12000034", "Governance & Finance", 0, 3),
        ("Aberdeenshire Council", "S12000034", "Biodiversity", 0, 1),
        ("Aberdeenshire Council", "S12000034", "Collaboration & Engagement", 0, 5),
        ("Aberdeenshire Council", "S12000034", "Waste Reduction & Food", 0, 5),
        ("Adur District Council", "E07000223", "Buildings & Heating", 0, 27),
        ("Adur District Council", "E07000223", "Transport", 1, 7),
        ("Adur District Council", "E07000223", "Planning & Land Use", 0, 4),
        ("Adur District Council", "E07000223", "Governance & Finance", 0, 3),
        ("Adur District Council", "E07000223", "Biodiversity", 0, 1),
        ("Adur District Council", "E07000223", "Collaboration & Engagement", 0, 5),
        ("Adur District Council", "E07000223", "Waste Reduction & Food", 0, 5),
    ]

    @mock.patch("crowdsourcer.management.commands.export_marks.Command.write_files")
    def test_export(self, write_mock):
        self.call_command("export_marks")

        percent, raw, linear = write_mock.call_args[0]
        self.assertEquals(raw, self.expected_raw)
        self.assertEquals(percent, self.expected_percent)
        self.assertEquals(linear, self.expected_linear)

    @mock.patch("crowdsourcer.management.commands.export_marks.Command.write_files")
    def test_export_with_unweighted_q(self, write_mock):
        Question.objects.filter(pk=272).update(weighting="unweighted")

        self.call_command("export_marks")

        self.expected_percent[0]["weighted_total"] = 0.009351851851851853

        percent, raw, linear = write_mock.call_args[0]
        self.assertEquals(raw, self.expected_raw)
        self.assertEquals(percent, self.expected_percent)
        self.assertEquals(linear, self.expected_linear)


class ExportWithMultiMarksTestCase(BaseCommandTestCase):
    fixtures = [
        "authorities.json",
        "basics.json",
        "users.json",
        "questions.json",
        "options.json",
        "audit_marking.json",
    ]

    @mock.patch("crowdsourcer.management.commands.export_marks.Command.write_files")
    def test_export(self, write_mock):
        self.call_command("export_marks")

        expected_percent = [
            {
                "council": "Aberdeen City Council",
                "gss": "S12000033",
                "Buildings & Heating": 0.10714285714285714,
                "Transport": 0.0,
                "Planning & Land Use": 0.0,
                "Governance & Finance": 0.0,
                "Biodiversity": 0.0,
                "Collaboration & Engagement": 0.0,
                "Waste Reduction & Food": 0.0,
                "raw_total": 0.05660377358490566,
                "weighted_total": 0.021041666666666667,
            },
            {
                "council": "Aberdeenshire Council",
                "gss": "S12000034",
                "Buildings & Heating": 0.0,
                "Transport": 0.2857142857142857,
                "Planning & Land Use": 0.0,
                "Governance & Finance": 0.0,
                "Biodiversity": 0.0,
                "Collaboration & Engagement": 0.0,
                "Waste Reduction & Food": 0.0,
                "raw_total": 0.03773584905660377,
                "weighted_total": 0.11666666666666668,
            },
            {
                "council": "Adur District Council",
                "gss": "E07000223",
                "Buildings & Heating": 0.0,
                "Transport": 0.42857142857142855,
                "Planning & Land Use": 0.0,
                "Governance & Finance": 0.0,
                "Biodiversity": 0.0,
                "Collaboration & Engagement": 0.0,
                "Waste Reduction & Food": 0.0,
                "raw_total": 0.057692307692307696,
                "weighted_total": 0.03333333333333334,
            },
        ]

        expected_raw = [
            {
                "Buildings & Heating": 3,
                "Transport": 0,
                "Planning & Land Use": 0,
                "Governance & Finance": 0,
                "Biodiversity": 0,
                "Collaboration & Engagement": 0,
                "Waste Reduction & Food": 0,
                "council": "Aberdeen City Council",
                "gss": "S12000033",
                "total": 3,
            },
            {
                "Buildings & Heating": 0,
                "Transport": 2,
                "Planning & Land Use": 0,
                "Governance & Finance": 0,
                "Biodiversity": 0,
                "Collaboration & Engagement": 0,
                "Waste Reduction & Food": 0,
                "council": "Aberdeenshire Council",
                "gss": "S12000034",
                "total": 2,
            },
            {
                "Buildings & Heating": 0,
                "Transport": 3,
                "Planning & Land Use": 0,
                "Governance & Finance": 0,
                "Biodiversity": 0,
                "Collaboration & Engagement": 0,
                "Waste Reduction & Food": 0,
                "council": "Adur District Council",
                "gss": "E07000223",
                "total": 3,
            },
        ]
        percent, raw, linear = write_mock.call_args[0]

        self.assertEquals(raw, expected_raw)
        self.assertEquals(percent, expected_percent)


class ExportWithMoreMarksTestCase(BaseCommandTestCase):
    fixtures = [
        "authorities.json",
        "basics.json",
        "users.json",
        "questions.json",
        "options.json",
        "audit_marking_many_marks.json",
    ]

    @mock.patch("crowdsourcer.management.commands.export_marks.Command.write_files")
    def test_export(self, write_mock):
        self.call_command("export_marks")

        expected_percent = [
            {
                "council": "Aberdeen City Council",
                "gss": "S12000033",
                "Buildings & Heating": 0.10714285714285714,
                "Transport": 0.0,
                "Planning & Land Use": 0.0,
                "Governance & Finance": 0.0,
                "Biodiversity": 0.0,
                "Collaboration & Engagement": 0.0,
                "Waste Reduction & Food": 0.0,
                "raw_total": 0.05660377358490566,
                "weighted_total": 0.021041666666666667,
            },
            {
                "council": "Aberdeenshire Council",
                "gss": "S12000034",
                "Buildings & Heating": 0.2857142857142857,
                "Transport": 1.0,
                "Planning & Land Use": 0.75,
                "Governance & Finance": 0.6666666666666666,
                "Biodiversity": 0.0,
                "Collaboration & Engagement": 0.2,
                "Waste Reduction & Food": 0.6,
                "raw_total": 0.4528301886792453,
                "weighted_total": 0.5427083333333333,
            },
            {
                "council": "Adur District Council",
                "gss": "E07000223",
                "Buildings & Heating": 0.0,
                "Transport": 0.42857142857142855,
                "Planning & Land Use": 0.0,
                "Governance & Finance": 0.0,
                "Biodiversity": 0.0,
                "Collaboration & Engagement": 0.0,
                "Waste Reduction & Food": 0.0,
                "raw_total": 0.057692307692307696,
                "weighted_total": 0.03333333333333334,
            },
        ]

        expected_raw = [
            {
                "Buildings & Heating": 3,
                "Transport": 0,
                "Planning & Land Use": 0,
                "Governance & Finance": 0,
                "Biodiversity": 0,
                "Collaboration & Engagement": 0,
                "Waste Reduction & Food": 0,
                "council": "Aberdeen City Council",
                "gss": "S12000033",
                "total": 3,
            },
            {
                "Buildings & Heating": 8,
                "Transport": 7,
                "Planning & Land Use": 3,
                "Governance & Finance": 2,
                "Biodiversity": 0,
                "Collaboration & Engagement": 1,
                "Waste Reduction & Food": 3,
                "council": "Aberdeenshire Council",
                "gss": "S12000034",
                "total": 24,
            },
            {
                "Buildings & Heating": 0,
                "Transport": 3,
                "Planning & Land Use": 0,
                "Governance & Finance": 0,
                "Biodiversity": 0,
                "Collaboration & Engagement": 0,
                "Waste Reduction & Food": 0,
                "council": "Adur District Council",
                "gss": "E07000223",
                "total": 3,
            },
        ]
        percent, raw, linear = write_mock.call_args[0]

        self.assertEquals(raw, expected_raw)
        self.assertEquals(percent, expected_percent)


class ExportNoMarksCATestCase(BaseCommandTestCase):
    fixtures = [
        "authorities.json",
        "authorities_ca.json",
        "basics.json",
        "ca_sections.json",
        "users.json",
        "questions.json",
        "options.json",
        "ca_questions.json",
    ]

    def test_max_calculation(self):
        (
            section,
            totals,
            q_maxes,
            weighted,
        ) = get_section_maxes()

        ca_max_section = {
            **max_section,
            **{
                "Buildings & Heating & Green Skills (CA)": {
                    "Single Tier": 0,
                    "District": 0,
                    "County": 0,
                    "Northern Ireland": 0,
                    "Combined Authority": 3,
                },
                "Transport (CA)": {
                    "Single Tier": 0,
                    "District": 0,
                    "County": 0,
                    "Northern Ireland": 0,
                    "Combined Authority": 1,
                },
                "Planning & Biodiversity (CA)": {
                    "Single Tier": 0,
                    "District": 0,
                    "County": 0,
                    "Northern Ireland": 0,
                    "Combined Authority": 1,
                },
                "Governance & Finance (CA)": {
                    "Single Tier": 0,
                    "District": 0,
                    "County": 0,
                    "Northern Ireland": 0,
                    "Combined Authority": 1,
                },
                "Collaboration & Engagement (CA)": {
                    "Single Tier": 0,
                    "District": 0,
                    "County": 0,
                    "Northern Ireland": 0,
                    "Combined Authority": 1,
                },
            },
        }

        ca_max_totals = max_totals.copy()
        ca_max_totals["Combined Authority"] = 7

        self.assertEquals(section, ca_max_section)
        self.assertEquals(totals, ca_max_totals)

    @mock.patch("crowdsourcer.management.commands.export_marks.Command.write_files")
    def test_export_with_no_marks(self, write_mock):
        self.call_command(
            "export_marks",
        )

        expected_percent = [
            {
                "council": "Aberdeen City Council",
                "gss": "S12000033",
                "Buildings & Heating": 0.0,
                "Transport": 0.0,
                "Planning & Land Use": 0.0,
                "Governance & Finance": 0.0,
                "Biodiversity": 0.0,
                "Collaboration & Engagement": 0.0,
                "Waste Reduction & Food": 0.0,
                "raw_total": 0.0,
                "weighted_total": 0.0,
            },
            {
                "council": "Aberdeenshire Council",
                "gss": "S12000034",
                "Buildings & Heating": 0.0,
                "Transport": 0.0,
                "Planning & Land Use": 0.0,
                "Governance & Finance": 0.0,
                "Biodiversity": 0.0,
                "Collaboration & Engagement": 0.0,
                "Waste Reduction & Food": 0.0,
                "raw_total": 0.0,
                "weighted_total": 0.0,
            },
            {
                "council": "Adur District Council",
                "gss": "E07000223",
                "Buildings & Heating": 0.0,
                "Transport": 0.0,
                "Planning & Land Use": 0.0,
                "Governance & Finance": 0.0,
                "Biodiversity": 0.0,
                "Collaboration & Engagement": 0.0,
                "Waste Reduction & Food": 0.0,
                "raw_total": 0.0,
                "weighted_total": 0.0,
            },
            {
                "council": "A Combined Authority",
                "gss": "S12000099",
                "Buildings & Heating & Green Skills (CA)": 0.0,
                "Transport (CA)": 0.0,
                "Planning & Biodiversity (CA)": 0.0,
                "Governance & Finance (CA)": 0.0,
                "Collaboration & Engagement (CA)": 0.0,
                "raw_total": 0.0,
                "weighted_total": 0.0,
            },
        ]

        expected_raw = [
            {
                "Buildings & Heating": 0,
                "Transport": 0,
                "Planning & Land Use": 0,
                "Governance & Finance": 0,
                "Biodiversity": 0,
                "Collaboration & Engagement": 0,
                "Waste Reduction & Food": 0,
                "council": "Aberdeen City Council",
                "gss": "S12000033",
                "total": 0,
            },
            {
                "Buildings & Heating": 0,
                "Transport": 0,
                "Planning & Land Use": 0,
                "Governance & Finance": 0,
                "Biodiversity": 0,
                "Collaboration & Engagement": 0,
                "Waste Reduction & Food": 0,
                "council": "Aberdeenshire Council",
                "gss": "S12000034",
                "total": 0,
            },
            {
                "Buildings & Heating": 0,
                "Transport": 0,
                "Planning & Land Use": 0,
                "Governance & Finance": 0,
                "Biodiversity": 0,
                "Collaboration & Engagement": 0,
                "Waste Reduction & Food": 0,
                "council": "Adur District Council",
                "gss": "E07000223",
                "total": 0,
            },
            {
                "council": "A Combined Authority",
                "Buildings & Heating & Green Skills (CA)": 0,
                "Transport (CA)": 0,
                "Planning & Biodiversity (CA)": 0,
                "Governance & Finance (CA)": 0,
                "Collaboration & Engagement (CA)": 0,
                "gss": "S12000099",
                "total": 0,
            },
        ]

        expected_linear = [
            ("Aberdeen City Council", "S12000033", "Buildings & Heating", 0, 28),
            ("Aberdeen City Council", "S12000033", "Transport", 0, 7),
            ("Aberdeen City Council", "S12000033", "Planning & Land Use", 0, 4),
            ("Aberdeen City Council", "S12000033", "Governance & Finance", 0, 3),
            ("Aberdeen City Council", "S12000033", "Biodiversity", 0, 1),
            ("Aberdeen City Council", "S12000033", "Collaboration & Engagement", 0, 5),
            ("Aberdeen City Council", "S12000033", "Waste Reduction & Food", 0, 5),
            ("Aberdeenshire Council", "S12000034", "Buildings & Heating", 0, 28),
            ("Aberdeenshire Council", "S12000034", "Transport", 0, 7),
            ("Aberdeenshire Council", "S12000034", "Planning & Land Use", 0, 4),
            ("Aberdeenshire Council", "S12000034", "Governance & Finance", 0, 3),
            ("Aberdeenshire Council", "S12000034", "Biodiversity", 0, 1),
            ("Aberdeenshire Council", "S12000034", "Collaboration & Engagement", 0, 5),
            ("Aberdeenshire Council", "S12000034", "Waste Reduction & Food", 0, 5),
            ("Adur District Council", "E07000223", "Buildings & Heating", 0, 27),
            ("Adur District Council", "E07000223", "Transport", 0, 7),
            ("Adur District Council", "E07000223", "Planning & Land Use", 0, 4),
            ("Adur District Council", "E07000223", "Governance & Finance", 0, 3),
            ("Adur District Council", "E07000223", "Biodiversity", 0, 1),
            ("Adur District Council", "E07000223", "Collaboration & Engagement", 0, 5),
            ("Adur District Council", "E07000223", "Waste Reduction & Food", 0, 5),
            (
                "A Combined Authority",
                "S12000099",
                "Buildings & Heating & Green Skills (CA)",
                0,
                3,
            ),
            ("A Combined Authority", "S12000099", "Transport (CA)", 0, 1),
            (
                "A Combined Authority",
                "S12000099",
                "Planning & Biodiversity (CA)",
                0,
                1,
            ),
            ("A Combined Authority", "S12000099", "Governance & Finance (CA)", 0, 1),
            (
                "A Combined Authority",
                "S12000099",
                "Collaboration & Engagement (CA)",
                0,
                1,
            ),
        ]

        percent, raw, linear = write_mock.call_args[0]
        self.assertEquals(percent, expected_percent)
        self.assertEquals(raw, expected_raw)
        self.assertEquals(linear, expected_linear)


class ExportWithMoreMarksCATestCase(BaseCommandTestCase):
    fixtures = [
        "authorities.json",
        "authorities_ca.json",
        "basics.json",
        "ca_sections.json",
        "users.json",
        "questions.json",
        "options.json",
        "ca_questions.json",
        "audit_marking_many_marks.json",
        "audit_ca_marks.json",
    ]

    expected_percent = [
        {
            "council": "Aberdeen City Council",
            "gss": "S12000033",
            "Buildings & Heating": 0.10714285714285714,
            "Transport": 0.0,
            "Planning & Land Use": 0.0,
            "Governance & Finance": 0.0,
            "Biodiversity": 0.0,
            "Collaboration & Engagement": 0.0,
            "Waste Reduction & Food": 0.0,
            "raw_total": 0.05660377358490566,
            "weighted_total": 0.021041666666666667,
        },
        {
            "council": "Aberdeenshire Council",
            "gss": "S12000034",
            "Buildings & Heating": 0.2857142857142857,
            "Transport": 1.0,
            "Planning & Land Use": 0.75,
            "Governance & Finance": 0.6666666666666666,
            "Biodiversity": 0.0,
            "Collaboration & Engagement": 0.2,
            "Waste Reduction & Food": 0.6,
            "raw_total": 0.4528301886792453,
            "weighted_total": 0.5427083333333333,
        },
        {
            "council": "Adur District Council",
            "gss": "E07000223",
            "Buildings & Heating": 0.0,
            "Transport": 0.42857142857142855,
            "Planning & Land Use": 0.0,
            "Governance & Finance": 0.0,
            "Biodiversity": 0.0,
            "Collaboration & Engagement": 0.0,
            "Waste Reduction & Food": 0.0,
            "raw_total": 0.057692307692307696,
            "weighted_total": 0.03333333333333334,
        },
        {
            "Buildings & Heating & Green Skills (CA)": 0.3333333333333333333,
            "Transport (CA)": 0.0,
            "Planning & Biodiversity (CA)": 1.0,
            "Governance & Finance (CA)": 1.0,
            "Collaboration & Engagement (CA)": 1.0,
            "council": "A Combined Authority",
            "gss": "S12000099",
            "raw_total": 0.5714285714285714,
            "weighted_total": 0.5833333333333334,
        },
    ]

    expected_raw = [
        {
            "Buildings & Heating": 3,
            "Transport": 0,
            "Planning & Land Use": 0,
            "Governance & Finance": 0,
            "Biodiversity": 0,
            "Collaboration & Engagement": 0,
            "Waste Reduction & Food": 0,
            "council": "Aberdeen City Council",
            "gss": "S12000033",
            "total": 3,
        },
        {
            "Buildings & Heating": 8,
            "Transport": 7,
            "Planning & Land Use": 3,
            "Governance & Finance": 2,
            "Biodiversity": 0,
            "Collaboration & Engagement": 1,
            "Waste Reduction & Food": 3,
            "council": "Aberdeenshire Council",
            "gss": "S12000034",
            "total": 24,
        },
        {
            "Buildings & Heating": 0,
            "Transport": 3,
            "Planning & Land Use": 0,
            "Governance & Finance": 0,
            "Biodiversity": 0,
            "Collaboration & Engagement": 0,
            "Waste Reduction & Food": 0,
            "council": "Adur District Council",
            "gss": "E07000223",
            "total": 3,
        },
        {
            "Buildings & Heating & Green Skills (CA)": 1,
            "Transport (CA)": 0,
            "Planning & Biodiversity (CA)": 1,
            "Governance & Finance (CA)": 1,
            "Collaboration & Engagement (CA)": 1,
            "council": "A Combined Authority",
            "gss": "S12000099",
            "total": 4,
        },
    ]

    @mock.patch("crowdsourcer.management.commands.export_marks.Command.write_files")
    def test_export(self, write_mock):
        self.call_command("export_marks")

        percent, raw, linear = write_mock.call_args[0]

        self.assertEquals(raw, self.expected_raw)
        self.assertEquals(percent, self.expected_percent)

    @mock.patch("crowdsourcer.management.commands.export_marks.Command.write_files")
    def test_export_100_percent(self, write_mock):

        Response.objects.filter(pk=37).update(option_id=196)
        Response.objects.get(pk=36).multi_option.add(195)

        self.call_command("export_marks")

        expected_raw = self.expected_raw.copy()
        expected_percent = self.expected_percent.copy()

        expected_raw[3] = {
            "Buildings & Heating & Green Skills (CA)": 3,
            "Transport (CA)": 1,
            "Planning & Biodiversity (CA)": 1,
            "Governance & Finance (CA)": 1,
            "Collaboration & Engagement (CA)": 1,
            "council": "A Combined Authority",
            "gss": "S12000099",
            "total": 7,
        }

        expected_percent[3] = {
            "council": "A Combined Authority",
            "gss": "S12000099",
            "Buildings & Heating & Green Skills (CA)": 1.0,
            "Transport (CA)": 1.0,
            "Planning & Biodiversity (CA)": 1.0,
            "Governance & Finance (CA)": 1.0,
            "Collaboration & Engagement (CA)": 1.0,
            "raw_total": 1.0,
            "weighted_total": 1.0,
        }
        percent, raw, linear = write_mock.call_args[0]

        self.assertEquals(raw, expected_raw)
        # import pprint

        # pprint.pp(percent)
        # pprint.pp(expected_percent)
        self.assertEquals(percent, expected_percent)
