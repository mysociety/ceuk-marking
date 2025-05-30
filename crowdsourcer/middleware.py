from django.conf import settings
from django.http import Http404

from crowdsourcer.models import MarkingSession, ResponseType


class AddStateMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        return response

    def process_view(self, request, view_func, view_args, view_kwargs):
        session_name = view_kwargs.get("marking_session", None)

        request.current_session = None
        request.current_stage = None

        if session_name is not None:
            current_session = MarkingSession.objects.filter(
                label=session_name, active=True
            ).first()
            if current_session is None:
                raise Http404
        else:
            current_session = (
                MarkingSession.objects.filter(active=True).order_by("-default").first()
            )

        if current_session is not None:
            current_stage = current_session.stage
            if current_stage is None:
                current_stage = ResponseType.objects.filter(type="First Mark").first()

            request.current_stage = current_stage
            request.current_session = current_session

    def process_template_response(self, request, response):
        context = response.context_data

        if request.current_session is not None:
            context["marking_session"] = request.current_session
            context["sessions"] = MarkingSession.objects.filter(active=True)
            context["brand"] = settings.BRAND
            context["brand_include"] = (
                f"crowdsourcer/cobrand/navbar_{context['brand']}.html"
            )

            response.context_data = context

        return response
