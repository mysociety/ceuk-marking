from django.db.models.query import QuerySet
from django.forms import (
    BaseFormSet,
    CheckboxSelectMultiple,
    HiddenInput,
    ModelForm,
    formset_factory,
)

from crowdsourcer.models import Option, Response


class ResponseFormSet(BaseFormSet):
    def _construct_form(self, i, **kwargs):
        if self.initial[i].get("id", None) is not None:
            response = Response.objects.get(id=self.initial[i]["id"])
            kwargs["instance"] = response

        form = super()._construct_form(i, **kwargs)
        return form


class ResponseForm(ModelForm):
    mandatory_if_no = ["private_notes"]
    mandatory_if_response = ["public_notes", "page_number", "evidence", "private_notes"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.authority_obj = self.initial.get("authority", None)
        self.question_obj = self.initial.get("question", None)

        self.fields["option"].queryset = Option.objects.filter(
            question=self.question_obj
        )

        self.fields["multi_option"].queryset = Option.objects.filter(
            question=self.question_obj
        )

    def clean(self):
        cleaned_data = super().clean()

        option_field = "option"
        if self.question_obj.question_type == "multiple_choice":
            option_field = "multi_option"

        response = cleaned_data.get(option_field, None)
        if isinstance(response, QuerySet):
            length = len(list(response))
            if length == 0:
                response = None
            elif length == 1:
                response = response.first()

        if response is None:
            values = False
            for field in self.mandatory_if_response:
                val = self.cleaned_data.get(field, None)
                if val is not None and val != "":
                    values = True

            if values:
                self.add_error(option_field, "This field is required")

        else:
            if str(response) in ["No", "None"]:
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
            "multi_option",
            "public_notes",
            "page_number",
            "evidence",
            "private_notes",
        ]
        widgets = {
            "authority": HiddenInput(),
            "question": HiddenInput(),
            "id": HiddenInput(),
            "multi_option": CheckboxSelectMultiple(),
        }


ResponseFormset = formset_factory(formset=ResponseFormSet, form=ResponseForm, extra=0)
