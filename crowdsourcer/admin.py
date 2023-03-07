from django.contrib import admin

from crowdsourcer.models import (
    Assigned,
    Marker,
    Option,
    PublicAuthority,
    Question,
    QuestionGroup,
    Response,
    ResponseType,
    Section,
)


@admin.register(Assigned)
class AssignedAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "section",
        "authority",
        "question",
    )
    search_fields = ["user__username", "authority__name"]
    list_filter = ["section", "authority__questiongroup"]


@admin.register(Option)
class OptionAdmin(admin.ModelAdmin):
    ordering = [
        "question__section",
        "question__number",
        "question__number_part",
        "ordering",
    ]
    list_filter = ["question__section", "question__question_type"]
    list_display = ("question", "description", "score", "ordering")


@admin.register(PublicAuthority)
class PublicAuthorityAdmin(admin.ModelAdmin):
    list_display = ("name", "questiongroup")
    list_filter = ["questiongroup", "do_not_mark"]
    search_fields = ["name"]
    ordering = ["name"]


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = (
        "section",
        "number",
        "number_part",
        "description",
    )
    list_filter = ["section", "how_marked", "questiongroup"]
    ordering = ("section", "number", "number_part")


@admin.register(QuestionGroup)
class QuestionGroupAdmin(admin.ModelAdmin):
    pass


@admin.register(Marker)
class MarkerAdmin(admin.ModelAdmin):
    list_display = ("user", "response_type", "authority")


@admin.register(Response)
class ResponseAdmin(admin.ModelAdmin):
    list_display = (
        "authority",
        "question",
        "response_type",
        "option",
    )

    search_fields = ["question__description", "authority__name"]
    list_filter = ["question__section"]


@admin.register(ResponseType)
class ResponseTypeAdmin(admin.ModelAdmin):
    pass


@admin.register(Section)
class SectionAdmin(admin.ModelAdmin):
    pass
