from django import template
from django.template.defaultfilters import stringfilter
from django.utils.html import Urlizer
from django.utils.safestring import mark_safe

from utils.data_checking import check_if_url_bad

register = template.Library()


class UrlizerExternal(Urlizer):
    url_template = (
        '<a href="{href}" target="_blank" title="Opens in new window"{attrs}>{url}</a>'
    )


urlizer_external = UrlizerExternal()


@register.filter(is_safe=True, needs_autoescape=True)
@stringfilter
def urlize_external(text, autoescape=True):
    """Convert URLs in plain text into clickable links with target="_blank" etc"""
    return mark_safe(
        urlizer_external(
            text, trim_url_limit=None, nofollow=True, autoescape=autoescape
        )
    )


@register.filter(is_safe=True, needs_autoescape=True)
@stringfilter
def check_if_broken(text, autoescape=True):
    if check_if_url_bad(text):
        return text
    else:
        return mark_safe(urlizer_external(text))
