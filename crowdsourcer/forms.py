from django.forms import ModelForm

from crowdsourcer.models import Response


class ResponseForm(ModelForm):
    class Meta:
        model = Response
        fields = ["authority", "question", "option", "public_notes", "private_notes"]
