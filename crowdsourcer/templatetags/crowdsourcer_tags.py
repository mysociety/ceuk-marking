from django import template
from django.template.defaulttags import url

register = template.Library()


class SessionURLNode(template.Node):
    def __init__(self, url_node):
        self.url_node = url_node

    def render(self, context):
        marking_session = context.get("marking_session", None)
        url = self.url_node.render(context)
        if marking_session is not None:
            url = f"/{marking_session}{url}"

        return url


@register.tag(name="session_url")
def session_url(parser, tokens):
    session_url = url(parser, tokens)
    node = SessionURLNode(session_url)

    return node
