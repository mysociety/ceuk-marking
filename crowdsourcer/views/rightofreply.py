import logging

from django.core.exceptions import PermissionDenied
from django.views.generic import TemplateView

from crowdsourcer.forms import RORResponseFormset
from crowdsourcer.models import PublicAuthority, Question, Response, ResponseType

logger = logging.getLogger(__name__)


class AuthorityRORSectionQuestions(TemplateView):
    template_name = "crowdsourcer/authority_ror_questions.html"
    model = Response

    def get_initial_obj(self):
        rt = ResponseType.objects.get(type="Right of Reply")
        authority = PublicAuthority.objects.get(name=self.kwargs["name"])
        questions = Question.objects.filter(
            section__title=self.kwargs["section_title"],
            questiongroup=authority.questiongroup,
            how_marked__in=["volunteer", "national_volunteer"],
        ).order_by("number", "number_part")
        responses = Response.objects.filter(
            authority=authority, question__in=questions, response_type=rt
        ).select_related("question")

        initial = {}
        for q in questions.all():
            data = {
                "authority": authority,
                "question": q,
            }
            initial[q.id] = data

        for r in responses:
            data = initial[r.question.id]
            data["id"] = r.id
            data["private_notes"] = r.private_notes

            initial[r.question.id] = data

        rt = ResponseType.objects.get(type="First Mark")
        responses = Response.objects.filter(
            authority=authority, question__in=questions, response_type=rt
        ).select_related("question")

        for r in responses:
            data = initial[r.question.id]
            data["original_response"] = r

            initial[r.question.id] = data

        return initial

    def get_form(self):
        if self.request.POST:
            formset = RORResponseFormset(
                self.request.POST, initial=list(self.get_initial_obj().values())
            )
        else:
            formset = RORResponseFormset(initial=list(self.get_initial_obj().values()))
        return formset

    def check_permissions(self):
        if self.request.user.is_anonymous:
            raise PermissionDenied

        if self.request.user.is_superuser is False:
            if hasattr(self.request.user, "marker"):
                marker = self.request.user.marker
                if (
                    marker.authority.name != self.kwargs["name"]
                    or marker.response_type.type != "Right of Reply"
                ):
                    raise PermissionDenied
            else:
                raise PermissionDenied

    def get(self, *args, **kwargs):
        self.check_permissions()
        return super().get(*args, **kwargs)

    def post(self, *args, **kwargs):
        self.check_permissions()
        section_title = self.kwargs.get("section_title", "")
        authority = self.kwargs.get("name", "")
        logger.debug(
            f"ROR form post from {self.request.user.email} for {authority}/{section_title}"
        )
        logger.debug(f"post data is {self.request.POST}")

        formset = self.get_form()
        rt = ResponseType.objects.get(type="Right of Reply")
        if formset.is_valid():
            logger.debug("form IS VALID")
            for form in formset:
                cleaned_data = form.cleaned_data
                if cleaned_data.get("agree_with_response", None) is not None:
                    form.instance.response_type = rt
                    form.instance.user = self.request.user
                    form.save()
                    logger.debug(f"saved form {form.prefix}")
                else:
                    logger.debug(f"did not save form {form.prefix}")
                    logger.debug(
                        f"agree_with_response is {cleaned_data.get('agree_with_response', None)}"
                    )
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
        ] = f"Right of Reply - {context['authority_name']}: {context['section_title']}"

        return context
