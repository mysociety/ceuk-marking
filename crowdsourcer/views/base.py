import logging

from django.contrib.auth.mixins import UserPassesTestMixin
from django.core.exceptions import PermissionDenied
from django.db.models import Count, F, FloatField, OuterRef, Subquery
from django.db.models.functions import Cast
from django.http import JsonResponse
from django.views.generic import ListView, TemplateView

from crowdsourcer.forms import ResponseForm, ResponseFormset
from crowdsourcer.models import (
    Assigned,
    PublicAuthority,
    Question,
    Response,
    ResponseType,
    Section,
)

logger = logging.getLogger(__name__)


class BaseQuestionView(TemplateView):
    model = Response
    formset = ResponseFormset
    response_type = "First Mark"
    log_start = "marking form"
    title_start = ""
    how_marked_in = ["volunteer", "national_volunteer"]
    has_previous_questions = False

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        try:
            self.rt = ResponseType.objects.get(type=self.response_type)
        except ResponseType.DoesNotExist:
            self.rt = None

    def check_local_permissions(self):
        return True

    def check_permissions(self):
        if self.request.user.is_anonymous:
            raise PermissionDenied

        if self.check_local_permissions() is False:
            raise PermissionDenied

        if not Assigned.is_user_assigned(
            self.request.user,
            authority=self.kwargs["name"],
            section=self.kwargs["section_title"],
            marking_session=self.request.current_session,
            current_stage=self.rt,
        ):
            raise PermissionDenied

    def get_initial_obj(self):
        self.authority = PublicAuthority.objects.get(name=self.kwargs["name"])
        self.questions = Question.objects.filter(
            section__marking_session=self.request.current_session,
            section__title=self.kwargs["section_title"],
            questiongroup=self.authority.questiongroup,
            how_marked__in=self.how_marked_in,
        ).order_by("number", "number_part")
        responses = Response.objects.filter(
            authority=self.authority, question__in=self.questions, response_type=self.rt
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

    def session_form_hash(self):
        return f"form-submission+{self.__class__.__name__}"

    def get_post_hash(self):
        excluded = {
            "csrfmiddlewaretoken",
        }
        post_hash = hash(
            tuple(
                sorted(
                    (k, v) for k, v in self.request.POST.items() if k not in excluded
                )
            )
        )

        return post_hash

    # there are occassional issues with the same form being resubmitted twice the first time
    # someone saves a result which means you get two responses saved for the same question which
    # leads to issues when exporting the data so add in some basic checking that this isn't a
    # repeat submission.
    def check_form_not_resubmitted(self, post_hash):
        previous_post_hash = self.request.session.get(self.session_form_hash())

        return post_hash != previous_post_hash

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
            post_hash = self.get_post_hash()
            if self.check_form_not_resubmitted(post_hash):
                logger.debug("form saved")
                for form in formset:
                    self.process_form(form)
                self.request.session[self.session_form_hash()] = post_hash
            else:
                logger.debug("form RESUBMITTED, not saving")
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
        context["page_title"] = (
            f"{self.title_start}{context['authority_name']}: {context['section_title']}"
        )
        context["has_previous_questions"] = self.has_previous_questions

        context["council_minutes"] = self.authority.get_data("council_minutes")
        return context


class BaseResponseJSONView(TemplateView):
    model = Response
    form = ResponseForm
    response_type = "First Mark"
    log_start = "marking form"
    title_start = ""
    how_marked_in = ["volunteer", "national_volunteer"]

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        try:
            self.rt = ResponseType.objects.get(type=self.response_type)
        except ResponseType.DoesNotExist:
            self.rt = None

    def check_local_permissions(self):
        return True

    def check_permissions(self):
        if self.request.user.is_anonymous:
            raise PermissionDenied

        if self.check_local_permissions() is False:
            raise PermissionDenied

        if not Assigned.is_user_assigned(
            self.request.user,
            authority=self.kwargs["name"],
            section=self.kwargs["section_title"],
            marking_session=self.request.current_session,
            current_stage=self.rt,
        ):
            raise PermissionDenied

    def get_initial_obj(self):
        self.authority = PublicAuthority.objects.get(name=self.kwargs["name"])
        self.question = Question.objects.get(id=self.kwargs["question"])
        instance = None
        initial = {
            "authority": self.authority,
            "question": self.question,
        }
        try:
            instance = Response.objects.get(
                authority=self.authority, question=self.question, response_type=self.rt
            )
            logger.debug(
                f"FOUND initial object for {self.authority}, {self.question}, {self.rt}"
            )
            for f in [
                "evidence",
                "id",
                "multi_option",
                "option",
                "page_number",
                "private_notes",
                "public_notes",
            ]:
                initial[f] = getattr(instance, f)
            logger.debug(f"initial data is {initial}")
        except Response.DoesNotExist:
            logger.debug(
                f"did NOT find initial object for {self.authority}, {self.question}, {self.rt}"
            )
            pass

        return {"initial": initial, "instance": instance}

    def get_form(self):
        initial = self.get_initial_obj()
        if self.request.POST:
            data = self.request.POST
            form = self.form(
                data, instance=initial["instance"], initial=initial["initial"]
            )
        else:
            form = self.form(instance=initial["instance"], initial=initial["initial"])
        return form

    def get(self, *args, **kwargs):
        return None

    def session_form_hash(self):
        return f"form-submission+{self.__class__.__name__}"

    def get_post_hash(self):
        excluded = {
            "csrfmiddlewaretoken",
        }
        post_hash = hash(
            tuple(
                sorted(
                    (k, v) for k, v in self.request.POST.items() if k not in excluded
                )
            )
        )

        return post_hash

    def post(self, *args, **kwargs):
        self.check_permissions()
        section_title = self.kwargs.get("section_title", "")
        authority = self.kwargs.get("name", "")
        logger.debug(
            f"{self.log_start} JSON post from {self.request.user.email} for {authority}/{section_title}"
        )
        logger.debug(f"post data is {self.request.POST}")

        form = self.get_form()
        logger.debug("got form")
        if form.is_valid():
            logger.debug("form IS VALID")
            post_hash = self.get_post_hash()
            if self.check_form_not_resubmitted(post_hash):
                logger.debug("form GOOD, saving")
                form.instance.response_type = self.rt
                form.instance.user = self.request.user
                form.save()
                self.request.session[self.session_form_hash()] = post_hash
            else:
                logger.debug("form RESUBMITTED, not saving")
        else:
            logger.debug(f"form NOT VALID, errors are {form.errors}")
            return JsonResponse({"success": 0, "errors": form.errors})

        print(form.instance)
        return JsonResponse({"success": 1})

    # there are occassional issues with the same form being resubmitted twice the first time
    # someone saves a result which means you get two responses saved for the same question which
    # leads to issues when exporting the data so add in some basic checking that this isn't a
    # repeat submission.
    def check_form_not_resubmitted(self, post_hash):
        previous_post_hash = self.request.session.get(self.session_form_hash())

        return post_hash != previous_post_hash


class BaseSectionAuthorityList(ListView):
    template_name = "crowdsourcer/section_authority_list.html"
    model = Section
    context_object_name = "authorities"
    types = ["volunteer", "national_volunteer"]
    question_page = "authority_question_edit"
    stage = "First Mark"

    def get_queryset(self):
        if self.request.user.is_anonymous:
            return None

        this_stage = ResponseType.objects.get(type=self.stage)

        if not Assigned.is_user_assigned(
            self.request.user,
            section=self.kwargs["section_title"],
            current_stage=this_stage,
        ):
            return None

        section = Section.objects.get(
            title=self.kwargs["section_title"],
            marking_session=self.request.current_session,
        )
        questions = Question.objects.filter(section=section, how_marked__in=self.types)

        question_list = list(questions.values_list("id", flat=True))

        assigned = None
        if not self.request.user.has_perm("crowdsourcer.can_view_all_responses"):
            assigned = Assigned.objects.filter(
                user=self.request.user,
                active=True,
                section=section,
                response_type=this_stage,
                authority__isnull=False,
            ).values_list("authority__id", flat=True)

        authorities = PublicAuthority.response_counts(
            question_list,
            self.kwargs["section_title"],
            self.request.user,
            self.request.current_session,
            assigned=assigned,
            question_types=self.types,
            response_type=this_stage,
        )

        return authorities.order_by("name").distinct()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["section_title"] = self.kwargs["section_title"]
        context["page_title"] = context["section_title"]
        context["question_page"] = self.question_page

        return context


class BaseAllSectionProgressView(UserPassesTestMixin, ListView):
    template_name = "crowdsourcer/all_section_progress.html"
    model = Section
    context_object_name = "sections"
    types = ["volunteer", "national_volunteer"]
    response_type = "First Mark"
    url_pattern = "section_progress"

    def test_func(self):
        return self.request.user.is_superuser

    def get_queryset(self):
        return Section.objects.filter(marking_session=self.request.current_session)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        rt = ResponseType.objects.get(type=self.response_type)

        progress = {}
        for section in context["sections"]:
            questions = Question.objects.filter(
                section=section, how_marked__in=self.types
            )
            question_list = list(questions.values_list("id", flat=True))
            authorities = PublicAuthority.response_counts(
                question_list,
                section.title,
                self.request.user,
                self.request.current_session,
                question_types=self.types,
                response_type=rt,
            ).distinct()

            total = 0
            complete = 0
            started = 0
            for authority in authorities:
                total = total + 1
                if authority.num_responses is not None and authority.num_responses > 0:
                    started = started + 1
                if (
                    authority.num_questions is not None
                    and authority.num_responses == authority.num_questions
                ):
                    complete = complete + 1

            progress[section.title] = {
                "total": total,
                "complete": complete,
                "started": started,
            }

        assigned = Section.objects.filter(
            marking_session=self.request.current_session
        ).annotate(
            num_authorities=Subquery(
                Assigned.objects.filter(section=OuterRef("pk"), response_type=rt)
                .values("section")
                .annotate(num_authorities=Count("pk"))
                .values("num_authorities")
            )
        )

        for section in assigned:
            progress[section.title]["assigned"] = section.num_authorities

        context["page_title"] = "Section Progress"
        context["progress"] = progress
        context["url_pattern"] = self.url_pattern

        return context


class BaseSectionProgressView(UserPassesTestMixin, ListView):
    template_name = "crowdsourcer/section_progress.html"
    model = Section
    context_object_name = "sections"
    types = ["volunteer", "national_volunteer"]
    response_type = "First Mark"
    url_pattern = "section_progress"

    def test_func(self):
        return self.request.user.is_superuser

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        section = Section.objects.get(
            title=self.kwargs["section_title"],
            marking_session=self.request.current_session,
        )
        questions = Question.objects.filter(section=section, how_marked__in=self.types)
        rt = ResponseType.objects.get(type=self.response_type)

        question_list = list(questions.values_list("id", flat=True))

        authorities = (
            PublicAuthority.response_counts(
                question_list,
                section.title,
                self.request.user,
                self.request.current_session,
                question_types=self.types,
                response_type=rt,
            )
            .distinct()
            .annotate(
                qs_left=Cast(F("num_responses"), FloatField())
                / Cast(F("num_questions"), FloatField())
            )
        )

        sort_order = self.request.GET.get("sort", None)
        if sort_order is None or sort_order != "asc":
            authorities = authorities.order_by(
                F("qs_left").desc(nulls_last=True), "name"
            )

        else:
            authorities = authorities.order_by(
                F("qs_left").asc(nulls_first=True), "name"
            )

        total = 0
        complete = 0
        for authority in authorities:
            total = total + 1
            if (
                authority.num_questions is not None
                and authority.num_responses == authority.num_questions
            ):
                complete = complete + 1

        context["page_title"] = f"{section.title} Section Progress"
        context["section"] = section
        context["totals"] = {"total": total, "complete": complete}
        context["authorities"] = authorities
        context["url_pattern"] = self.url_pattern

        return context


class BaseAuthorityAssignmentView(UserPassesTestMixin, ListView):
    template_name = "crowdsourcer/authorities_assigned.html"
    model = PublicAuthority
    context_object_name = "authorities"
    stage = "First Mark"

    def test_func(self):
        return self.request.user.is_superuser

    def get_queryset(self):
        rt = ResponseType.objects.get(type=self.stage)
        qs = (
            PublicAuthority.objects.filter(
                marking_session=self.request.current_session,
                questiongroup__marking_session=self.request.current_session,
            )
            .annotate(
                num_sections=Subquery(
                    Assigned.objects.filter(
                        authority=OuterRef("pk"),
                        response_type=rt,
                        section__marking_session=self.request.current_session,
                    )
                    .values("authority")
                    .annotate(num_sections=Count("pk"))
                    .values("num_sections")
                )
            )
            .annotate(
                total_sections=Subquery(
                    Question.objects.filter(
                        questiongroup=OuterRef("questiongroup"),
                        section__marking_session=self.request.current_session,
                    )
                    .values("section__marking_session__id")
                    .annotate(total_sections=Count("section_id", distinct=True))
                    .values("total_sections")
                )
            )
        )

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        authorities = context["authorities"]
        sort_order = self.request.GET.get("sort", None)
        do_not_mark_only = self.request.GET.get("do_not_mark_only", None)

        if do_not_mark_only is not None:
            authorities = authorities.filter(do_not_mark=True)

        if sort_order is None or sort_order != "asc":
            authorities = authorities.order_by(
                F("num_sections").desc(nulls_last=True), "name"
            )

        else:
            authorities = authorities.order_by(
                F("num_sections").asc(nulls_first=True), "name"
            )

        context["authorities"] = authorities
        context["do_not_mark_only"] = do_not_mark_only

        return context
