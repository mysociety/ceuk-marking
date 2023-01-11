from django.forms import BaseFormSet, HiddenInput, ModelForm, formset_factory

from crowdsourcer.models import Option, Response


class ResponseFormSet(BaseFormSet):
    def _construct_form(self, i, **kwargs):
        print(self.initial)
        if self.initial[i].get("id", None) is not None:
            response = Response.objects.get(id=self.initial[i]["id"])
            kwargs["instance"] = response

        form = super()._construct_form(i, **kwargs)
        return form


class ResponseForm(ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.authority_obj = self.initial.get("authority", None)
        self.question_obj = self.initial.get("question", None)

        self.fields["option"].queryset = Option.objects.filter(
            question=self.question_obj
        )

    class Meta:
        model = Response
        fields = [
            "id",
            "authority",
            "question",
            "option",
            "public_notes",
            "private_notes",
        ]
        widgets = {
            "authority": HiddenInput(),
            "question": HiddenInput(),
            "id": HiddenInput(),
        }


ResponseFormset = formset_factory(formset=ResponseFormSet, form=ResponseForm, extra=0)
