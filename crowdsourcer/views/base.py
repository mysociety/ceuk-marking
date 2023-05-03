import logging

from django.views.generic import TemplateView

from crowdsourcer.forms import ResponseFormset
from crowdsourcer.models import PublicAuthority, Question, Response, ResponseType

logger = logging.getLogger(__name__)


class BaseQuestionView(TemplateView):
    model = Response
    formset = ResponseFormset
    response_type = "First Mark"
    log_start = "marking form"
    title_start = ""
    how_marked_in = ["volunteer", "national_volunteer"]

    def get_initial_obj(self):
        rt = ResponseType.objects.get(type=self.response_type)
        self.authority = PublicAuthority.objects.get(name=self.kwargs["name"])
        self.questions = Question.objects.filter(
            section__title=self.kwargs["section_title"],
            questiongroup=self.authority.questiongroup,
            how_marked__in=self.how_marked_in,
        ).order_by("number", "number_part")
        responses = Response.objects.filter(
            authority=self.authority, question__in=self.questions, response_type=rt
        ).select_related("question")

        initial = {}
        for q in self.questions.all():
            data = {
                "authority": self.authority,
                "question": q,
            }
            initial[q.id] = data

        for r in responses:
            data = initial[r.question.id]
            data["id"] = r.id
            data["private_notes"] = r.private_notes

            initial[r.question.id] = data

        return initial

    def get_form(self):
        if self.request.POST:
            formset = self.formset(
                self.request.POST, initial=list(self.get_initial_obj().values())
            )
        else:
            formset = self.formset(initial=list(self.get_initial_obj().values()))
        return formset

    def get(self, *args, **kwargs):
        self.check_permissions()
        return super().get(*args, **kwargs)

    def post(self, *args, **kwargs):
        self.check_permissions()
        section_title = self.kwargs.get("section_title", "")
        authority = self.kwargs.get("name", "")
        logger.debug(
            f"{self.log_start} post from {self.request.user.email} for {authority}/{section_title}"
        )
        logger.debug(f"post data is {self.request.POST}")

        formset = self.get_form()
        if formset.is_valid():
            logger.debug("form IS VALID")
            for form in formset:
                self.process_form(form)
        else:
            logger.debug(f"form NOT VALID, errors are {formset.errors}")
            return self.render_to_response(self.get_context_data(form=formset))

        context = self.get_context_data()
        context["message"] = "Your answers have been saved."
        return self.render_to_response(context)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["form"] = self.get_form()
        context["section_title"] = self.kwargs.get("section_title", "")
        context["authority"] = PublicAuthority.objects.get(
            name=self.kwargs.get("name", "")
        )
        context["authority_name"] = self.kwargs.get("name", "")
        context[
            "page_title"
        ] = f"{self.title_start}{context['authority_name']}: {context['section_title']}"

        context["ror_user"] = True

        return context
