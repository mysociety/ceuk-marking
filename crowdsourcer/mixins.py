from crowdsourcer.models import ResponseType


class CurrentStageMixin:
    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        current_stage = ResponseType.objects.filter(active=True).first()
        if current_stage is None:
            current_stage = ResponseType.objects.get(type="First Mark")

        self.current_stage = current_stage
