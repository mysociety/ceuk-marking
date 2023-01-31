from django.conf import settings
from django.core.management.base import BaseCommand

import pandas as pd

from crowdsourcer.models import Option, PublicAuthority, Question, Response, Section


class Command(BaseCommand):
    help = "export Right Of Reply Excel Sheet"

    outfile = settings.BASE_DIR / "data" / "right_of_reply.xlsx"

    def handle(self, *args, **options):
        council = PublicAuthority.objects.get(name="Aberdeen City Council")
        question_group = council.questiongroup

        with pd.ExcelWriter(self.outfile, engine="xlsxwriter") as writer:
            for section in Section.objects.all():
                questions = Question.objects.filter(
                    questiongroup=question_group,
                    section=section,
                    how_marked__in=["volunteer", "national_volunteer"],
                )

                out = []
                for question in questions:
                    answers = Response.objects.filter(
                        question=question,
                        authority=council,
                    ).order_by("question__number", "question__number_part")

                    answer_list = []
                    for answer in answers:
                        answer_list.append(answer.option.description)

                    out.append(
                        {
                            "question_no": question.number,
                            "question_part": question.number_part,
                            "question": question.description,
                            "response": ",".join(answer_list),
                            "answer": "",
                        }
                    )

                df = pd.DataFrame(out)
                df.to_excel(writer, sheet_name=section.title, index=False)

                index = 2
                for question in questions:
                    options = Option.objects.filter(question=question).order_by(
                        "ordering"
                    )
                    opt_list = []
                    for opt in options:
                        opt_list.append(opt.description)

                    sheet = writer.sheets[section.title]
                    sheet.data_validation(
                        f"E{index}", {"validate": "list", "source": opt_list}
                    )

                    index = index + 1
