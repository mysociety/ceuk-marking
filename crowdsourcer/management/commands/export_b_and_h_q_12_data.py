from django.conf import settings
from django.core.management.base import BaseCommand

import pandas as pd

from crowdsourcer.models import Question, Response, Section


class Command(BaseCommand):
    help = "Export Buildings and Heating Q12 data to csv"

    export_file = settings.BASE_DIR / "data" / "b_and_h_q_12.csv"

    sections = [
        "Buildings & Heating",
    ]

    def handle(self, *args, **options):
        data = []
        for title in self.sections:
            section = Section.objects.get(title=title)

            q = Question.objects.get(section=section, number=12)
            responses = Response.objects.filter(
                question=q, response_type__type="First Mark"
            ).select_related("authority", "option")

            for response in responses:
                defaults = {
                    "authority": response.authority.name,
                    "gss_code": response.authority.unique_id,
                    "evidence": response.evidence,
                    "page_no": response.page_number,
                    "public_notes": response.public_notes,
                    "private_notes:": response.private_notes,
                }

                if response.option:
                    defaults["answer"] = response.option.description
                if response.multi_option.count() > 0:
                    answers = []
                    for opt in response.multi_option.all():
                        answers.append(opt.description)
                    defaults["answer"] = ", ".join(answers)

                data.append(defaults)

        df = pd.DataFrame(data)
        df.to_csv(self.export_file, index=False)
