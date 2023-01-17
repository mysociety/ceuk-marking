from django.forms import BaseFormSet, HiddenInput, ModelForm, formset_factory

from crowdsourcer.models import Option, Response


class ResponseFormSet(BaseFormSet):
    def _construct_form(self, i, **kwargs):
        if self.initial[i].get("id", None) is not None:
            response = Response.objects.get(id=self.initial[i]["id"])
            kwargs["instance"] = response

        form = super()._construct_form(i, **kwargs)
        return form


class ResponseForm(ModelForm):
    mandatory_if_no = ["private_evidence"]
    mandatory_if_response = ["public_notes", "page_number", "evidence", "private_notes"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.authority_obj = self.initial.get("authority", None)
        self.question_obj = self.initial.get("question", None)

        self.fields["option"].queryset = Option.objects.filter(
            question=self.question_obj
        )

    def clean(self):
        cleaned_data = super().clean()

        response = cleaned_data.get("option", None)

        if response is None:
            values = False
            for field in self.mandatory_if_response:
                val = self.cleaned_data.get(field, None)
                if val is not None and val != "":
                    values = True

            if values:
                self.add_error("option", "This field is required")

        else:
            if response in ["No", "None"]:
                mandatory = self.mandatory_if_no
            else:
                mandatory = self.mandatory_if_response

            for field in mandatory:
                value = cleaned_data.get(field, None)
                if value is None or value == "":
                    self.add_error(field, "This field is required")

        return cleaned_data

    class Meta:
        model = Response
        fields = [
            "id",
            "authority",
            "question",
            "option",
            "public_notes",
            "page_number",
            "evidence",
            "private_notes",
        ]
        widgets = {
            "authority": HiddenInput(),
            "question": HiddenInput(),
            "id": HiddenInput(),
        }


ResponseFormset = formset_factory(formset=ResponseFormSet, form=ResponseForm, extra=0)
