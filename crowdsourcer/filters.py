from django.contrib.auth.models import User
from django.db.models import Q

import django_filters

from crowdsourcer.models import Option, Question, Response, ResponseType, Section


def filter_not_empty(queryset, name, value):
    lookup = "__".join([name, "isnull"])
    return queryset.filter(**{lookup: not value})


class VolunteerFilter(django_filters.FilterSet):
    has_assignments = django_filters.BooleanFilter(
        field_name="num_assignments", method=filter_not_empty, label="Has assignments"
    )
    marker__response_type = django_filters.ChoiceFilter(
        label="Stage", choices=ResponseType.choices()
    )
    assigned_section = django_filters.ChoiceFilter(
        field_name="assigned_section",
        label="Assigned Section",
        lookup_expr="icontains",
        choices=Section.objects.values_list("title", "title"),
    )
    # have to specify it like this otherwise bootstrap doesn't recognise it as a bound field
    username = django_filters.CharFilter(field_name="username", lookup_expr="icontains")

    class Meta:
        model = User
        fields = {
            "marker__response_type": ["exact"],
            "is_active": ["exact"],
        }


class ResponseFilter(django_filters.FilterSet):
    response_type = django_filters.ChoiceFilter(
        label="Stage",
        choices=ResponseType.choices(),
        method="response_type_check",
    )
    question__section = django_filters.ChoiceFilter(
        label="Section",
        empty_label=None,
        choices=Section.objects.values_list("id", "title"),
    )
    question = django_filters.ChoiceFilter(
        field_name="question",
        label="Question",
        choices=Question.objects.values_list("id", "number"),
    )
    option = django_filters.ChoiceFilter(
        field_name="option",
        label="Answer",
        method="option_check",
        choices=Option.objects.values_list("id", "description"),
    )

    def option_check(self, queryset, name, value):
        queryset = queryset.filter(Q(option=value) | Q(multi_option=value))
        return queryset

    def response_type_check(self, queryset, name, value):
        if value != "":
            queryset = queryset.filter(**{name: value})
        return queryset

    class Meta:
        model = Response
        fields = {
            "question": ["exact"],
            "option": ["exact"],
        }
