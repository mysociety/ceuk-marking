import logging

from django.core.exceptions import PermissionDenied

from crowdsourcer.forms import AuditResponseFormset
from crowdsourcer.models import Assigned, Response, ResponseType
from crowdsourcer.views.base import BaseQuestionView, BaseSectionAuthorityList

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

    def check_permissions(self):
        if self.request.user.is_anonymous:
            raise PermissionDenied

        rt = ResponseType.objects.get(type=self.response_type)
        user = self.request.user
        if user.is_superuser is False:
            if hasattr(user, "marker"):
                marker = user.marker
                if marker.response_type.type == "Audit":
                    if not Assigned.is_user_assigned(
                        user=user,
                        authority=self.kwargs["name"],
                        section=self.kwargs["section_title"],
                        current_stage=rt,
                    ):
                        raise PermissionDenied
                else:
                    raise PermissionDenied

            else:
                raise PermissionDenied

    def process_form(self, form):
        rt = ResponseType.objects.get(type=self.response_type)
        cleaned_data = form.cleaned_data
        # XXX work out what the field is
        if (
            cleaned_data.get("option", None) is not None
            or len(list(cleaned_data.get("multi_option", None))) > 0
        ):
            form.instance.response_type = rt
            form.instance.user = self.request.user
            form.save()
            logger.debug(f"saved form {form.prefix}")
        elif form.initial.get("id", None) is not None:
            form.save()
            logger.debug(f"saved blank form {form.prefix}")
        else:
            logger.debug(f"did not save form {form.prefix}")
            logger.debug(
                f"agree_with_response is {cleaned_data.get('agree_with_response', None)}"
            )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["audit_user"] = True
        return context
