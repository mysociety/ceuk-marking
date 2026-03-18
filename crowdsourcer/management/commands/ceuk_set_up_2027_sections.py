from django.core.management.base import BaseCommand

from crowdsourcer.models import MarkingSession, QuestionGroup, Section


class Command(BaseCommand):
    help = "set up 2027 sections"

    session = "Scorecards 2027"

    sections_ma = [
        "Buildings & Heating (MA)",
        "Transport (MA)",
        "Planning & Biodiversity (MA)",
        "Governance & Finance (MA)",
        "Collaboration & Engagement (MA)",
    ]

    sections = [
        "Governance & Finance",
        "Planning & Land Use",
        "Collaboration & Engagement",
        "Buildings & Heating",
        "Biodiversity",
        "Transport",
        "Waste Reduction & Food",
    ]

    question_groups = [
        "Combined Authority",
        "Northern Ireland",
        "County",
        "District",
        "Single Tier",
    ]

    def handle(self, *args, **options):
        print("Creating sections")

        session = MarkingSession.objects.get(label=self.session)

        all_sections = self.sections + self.sections_ma

        for section in all_sections:
            s, _ = Section.objects.get_or_create(title=section, marking_session=session)

        for group in self.question_groups:
            g, _ = QuestionGroup.objects.get_or_create(description=group)
            g.marking_session.add(session)
