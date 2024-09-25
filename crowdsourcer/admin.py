from django.contrib import admin
from django.contrib.admin import SimpleListFilter

from crowdsourcer.models import (
    Assigned,
    Marker,
    MarkingSession,
    Option,
    PublicAuthority,
    Question,
    QuestionGroup,
    Response,
    ResponseType,
    Section,
)


class SectionFilter(SimpleListFilter):
    title = "section"

    parameter_name = "section"

    def lookups(self, request, model_admin):
        qs = model_admin.get_queryset(request)
        lookups = []
        for section in Section.objects.filter(
            pk__in=qs.values_list("section", flat=True).distinct()
        ).order_by("marking_session", "title"):
            lookups.append((section.id, section))

        return lookups

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(section=self.value())


@admin.register(Assigned)
class AssignedAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "section",
        "authority",
        "response_type",
    )
    search_fields = ["user__username", "authority__name"]
    list_filter = [
        "section__marking_session",
        "section",
        "authority__questiongroup",
        "response_type",
        "active",
    ]


@admin.register(Option)
class OptionAdmin(admin.ModelAdmin):
    ordering = [
        "question__section",
        "question__number",
        "question__number_part",
        "ordering",
    ]
    list_filter = ["question__section", "question__question_type"]
    list_display = (
        "question",
        "description",
        "score",
        "ordering",
    )


@admin.register(PublicAuthority)
class PublicAuthorityAdmin(admin.ModelAdmin):
    list_display = ("name", "questiongroup")
    list_filter = ["questiongroup", "do_not_mark", "marking_session"]
    search_fields = ["name"]
    ordering = ["name"]


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = (
        "section",
        "number",
        "number_part",
        "description",
        "weighting",
    )
    list_filter = [
        "section__marking_session",
        "how_marked",
        "question_type",
        "questiongroup",
        SectionFilter,
    ]
    ordering = ("section", "number", "number_part")


@admin.register(QuestionGroup)
class QuestionGroupAdmin(admin.ModelAdmin):
    pass


@admin.register(Marker)
class MarkerAdmin(admin.ModelAdmin):
    list_display = ("user", "response_type", "authority")
    search_fields = ["user__username"]
    list_filter = ["response_type"]


@admin.register(Response)
class ResponseAdmin(admin.ModelAdmin):
    list_display = (
        "authority",
        "question",
        "response_type",
        "option",
    )

    search_fields = ["question__description", "authority__name"]
    list_filter = [
        "question__section__marking_session",
        "question__section",
        "response_type",
    ]


@admin.register(ResponseType)
class ResponseTypeAdmin(admin.ModelAdmin):
    pass


@admin.register(Section)
class SectionAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "marking_session",
    )

    list_filter = ["marking_session"]


@admin.register(MarkingSession)
class MarkingSessionAdmin(admin.ModelAdmin):
    pass
