from django.core.management.base import BaseCommand

from crowdsourcer.models import MarkingSession, SessionConfig

SECTION_WEIGHTINGS = {
    "Buildings & Heating": {
        "Single Tier": 0.20,
        "District": 0.25,
        "County": 0.20,
        "Northern Ireland": 0.20,
    },
    "Transport": {
        "Single Tier": 0.20,
        "District": 0.05,
        "County": 0.30,
        "Northern Ireland": 0.15,
    },
    "Planning & Land Use": {
        "Single Tier": 0.15,
        "District": 0.25,
        "County": 0.05,
        "Northern Ireland": 0.15,
    },
    "Governance & Finance": {
        "Single Tier": 0.15,
        "District": 0.15,
        "County": 0.15,
        "Northern Ireland": 0.20,
    },
    "Biodiversity": {
        "Single Tier": 0.10,
        "District": 0.10,
        "County": 0.10,
        "Northern Ireland": 0.10,
    },
    "Collaboration & Engagement": {
        "Single Tier": 0.10,
        "District": 0.10,
        "County": 0.10,
        "Northern Ireland": 0.10,
    },
    "Waste Reduction & Food": {
        "Single Tier": 0.10,
        "District": 0.10,
        "County": 0.10,
        "Northern Ireland": 0.10,
    },
    "Transport (CA)": {
        "Combined Authority": 0.25,
    },
    "Buildings & Heating & Green Skills (CA)": {
        "Combined Authority": 0.25,
    },
    "Governance & Finance (CA)": {
        "Combined Authority": 0.20,
    },
    "Planning & Biodiversity (CA)": {
        "Combined Authority": 0.10,
    },
    "Collaboration & Engagement (CA)": {
        "Combined Authority": 0.20,
    },
}

EXCEPTIONS = {
    "Transport": {
        "Single Tier": {
            "scotland": ["6", "8b"],
            "wales": ["6", "8b"],
        },
        "LBO": ["6"],
        "Greater London Authority": ["6"],
    },
    "Biodiversity": {
        "Single Tier": {
            "scotland": ["4"],
            "wales": ["4"],
        }
    },
    "Buildings & Heating": {
        "Single Tier": {
            "scotland": ["8"],
        },
        "Northern Ireland": {
            "northern ireland": ["8"],
        },
    },
    "Waste Reduction & Food": {
        "CTY": ["1b"],
    },
}

SCORE_EXCEPTIONS = {
    "Waste Reduction & Food": {
        "2": {
            "max_score": 1,
            "points_for_max": 2,
        }
    }
}


class Command(BaseCommand):
    help = "set up config for exceptions and weightings in database"

    sessions = ["Scorecards 2023", "Scorecards 2025"]

    conf_map = {
        "exceptions": EXCEPTIONS,
        "score_exceptions": SCORE_EXCEPTIONS,
        "score_weightings": SECTION_WEIGHTINGS,
    }

    def handle(self, *args, **kwargs):
        for session in self.sessions:
            ms = MarkingSession.objects.get(label=session)
            for name, conf in self.conf_map.items():
                c = SessionConfig.objects.filter(name=name, marking_session=ms)
                if not c.exists():
                    SessionConfig.objects.create(
                        name=name,
                        marking_session=ms,
                        config_type="json",
                        json_value=conf,
                    )
