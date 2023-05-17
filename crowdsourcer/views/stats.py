import csv
import logging
from collections import defaultdict

from django.contrib.auth.mixins import UserPassesTestMixin
from django.db.models import Count
from django.http import HttpResponse
from django.views.generic import ListView

from crowdsourcer.models import Question, Response

logger = logging.getLogger(__name__)


class AllMarksBaseCSVView(UserPassesTestMixin, ListView):
    context_object_name = "responses"
    response_type = "First Mark"
    file_name = "grace_first_mark_scores.csv"

    def test_func(self):
        return self.request.user.is_superuser

    def get_queryset(self):
        return (
            Response.objects.filter(response_type__type=self.response_type)
            .select_related("question", "authority", "question__section", "option")
            .order_by(
                "authority",
                "question__section__title",
                "question__number",
                "question__number_part",
            )
            .annotate(multi_count=Count("multi_option__pk"))
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        responses = defaultdict(dict)
        questions = (
            Question.objects.select_related("section")
            .all()
            .order_by("section__title", "number", "number_part")
        )

        headers = {}
        for q in questions:
            q_desc = f"{q.section.title}: {q.number_and_part}"
            headers[q_desc] = 1

        for response in context["responses"]:
            score = 0

            if response.multi_count > 0:
                for opt in response.multi_option.all():
                    score += opt.score
            elif response.option is not None:
                score = response.option.score
            else:
                score = "-"

            q = response.question
            q_desc = f"{q.section.title}: {q.number_and_part}"

            responses[response.authority.name][q_desc] = score

        context["headers"] = sorted(headers.keys())
        context["marks"] = responses

        return context

    def render_to_response(self, context, **response_kwargs):
        response = HttpResponse(
            content_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{self.file_name}"'},
        )
        writer = csv.writer(response)
        headers = [
            "authority",
        ] + context["headers"]
        writer.writerow(headers)
        for authority, mark in context["marks"].items():
            row = [authority] + [mark.get(q, "-") for q in context["headers"]]
            writer.writerow(row)
        return response


class AllFirstMarksCSVView(AllMarksBaseCSVView):
    pass


class AllAuditMarksCSVView(AllMarksBaseCSVView):
    response_type = "Audit"
    file_name = "grace_audit_mark_scores.csv"
