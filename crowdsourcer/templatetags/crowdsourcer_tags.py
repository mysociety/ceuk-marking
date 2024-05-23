from django import template
from django.template.defaulttags import url

import markdown

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


@register.tag(name="markdown")
def markdown_tag(parser, token):
    """
    Between {% markdown %} and {% endmarkdown %} tags,
    render the text as markdown.

    Django tags used within the markdown will be rendered first.
    """
    nodelist = parser.parse(("endmarkdown",))
    parser.delete_first_token()
    return MarkdownNode(nodelist)


class MarkdownNode(template.Node):
    def __init__(self, nodelist):
        self.nodelist = nodelist

    def render(self, context):
        # render items below in the stack into markdown
        markdown_text = self.nodelist.render(context)

        # if the text is indented, we want to remove the indentation so that the smallest indent becomes 0, but all others are relative to that
        # this is so that we can have indented code blocks in markdown
        # we do this by finding the smallest indent, and then removing that from all lines

        smallest_indent = None
        for line in markdown_text.splitlines():
            if line.strip() == "":
                continue
            indent = len(line) - len(line.lstrip())
            if smallest_indent is None or indent < smallest_indent:
                smallest_indent = indent

        # remove the smallest indent from all lines
        if smallest_indent is not None:
            markdown_text = "\n".join(
                [line[smallest_indent:] for line in markdown_text.splitlines()]
            )

        text = markdown.markdown(markdown_text, extensions=["toc"])
        return text
