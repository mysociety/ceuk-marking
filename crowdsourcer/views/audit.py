import logging

from crowdsourcer.forms import AuditResponseFormset
from crowdsourcer.models import Response, ResponseType
from crowdsourcer.views.base import (
    BaseQuestionView,
    BaseResponseJSONView,
    BaseSectionAuthorityList,
)

logger = logging.getLogger(__name__)


class SectionAuthorityList(BaseSectionAuthorityList):
    types = ["volunteer", "national_volunteer", "foi"]
    question_page = "authority_audit"
    stage = "Audit"


class AuthorityAuditSectionQuestions(BaseQuestionView):
    template_name = "crowdsourcer/authority_audit_questions.html"
    model = Response
    formset = AuditResponseFormset
    response_type = "Audit"
    log_start = "Audit form"
    title_start = "Audit - "
    how_marked_in = ["volunteer", "national_volunteer", "foi", "national_data"]

    def get_initial_obj(self):
        initial = super().get_initial_obj()

        first_rt = ResponseType.objects.get(type="First Mark")
        ror_rt = ResponseType.objects.get(type="Right of Reply")

        first_responses = Response.objects.filter(
            authority=self.authority,
            question__in=self.questions,
            response_type=first_rt,
        ).select_related("question")

        ror_responses = Response.objects.filter(
            authority=self.authority, question__in=self.questions, response_type=ror_rt
        ).select_related("question")

        for r in first_responses:
            data = initial[r.question.id]
            data["original_response"] = r

            initial[r.question.id] = data

        for r in ror_responses:
            data = initial[r.question.id]
            data["ror_response"] = r

            initial[r.question.id] = data

        return initial

    def check_local_permissions(self):
        permitted = False

        user = self.request.user
        if user.has_perm("crowdsourcer.can_view_all_responses"):
            permitted = True
        elif hasattr(user, "marker") and user.marker.response_type.type == "Audit":
            permitted = True

        return permitted

    def process_form(self, form):
        log_start = f"[{self.request.user.id}-{self.authority.id}-{self.section.id}]"
        cleaned_data = form.cleaned_data
        # XXX work out what the field is
        if (
            cleaned_data.get("option", None) is not None
            or len(list(cleaned_data.get("multi_option", None))) > 0
        ):
            form.instance.response_type = self.rt
            form.instance.user = self.request.user
            form.save()
            logger.debug(f"{log_start} saved form {form.prefix}")
        elif form.initial.get("id", None) is not None:
            form.save()
            logger.debug(f"{log_start} saved blank form {form.prefix}")
        else:
            logger.debug(f"{log_start} did not save form {form.prefix}")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["audit_user"] = True
        return context


class AuthorityAuditSectionJSONQuestion(BaseResponseJSONView):
    response_type = "Audit"
