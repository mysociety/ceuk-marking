from django.contrib.auth.models import User

import django_filters

from crowdsourcer.models import ResponseType, Section


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
