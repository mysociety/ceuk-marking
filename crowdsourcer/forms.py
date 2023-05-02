from django.core.validators import validate_comma_separated_integer_list
from django.db.models.query import QuerySet
from django.forms import (
    BaseFormSet,
    CheckboxSelectMultiple,
    HiddenInput,
    ModelForm,
    Select,
    Textarea,
    TextInput,
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

    def clean_page_number(self):
        page_number = self.cleaned_data["page_number"]
        if page_number == "" or page_number is None:
            return page_number
        validate_comma_separated_integer_list(page_number)
        return page_number

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
            "authority",
            "evidence",
            "id",
            "multi_option",
            "option",
            "page_number",
            "private_notes",
            "public_notes",
            "question",
        ]
        widgets = {
            "authority": HiddenInput(),
            "evidence": Textarea(
                attrs={
                    # "placeholder": False,
                    "rows": 3,
                }
            ),
            "id": HiddenInput(),
            "option": Select(
                attrs={
                    # "placeholder": False,
                }
            ),
            "multi_option": CheckboxSelectMultiple(),
            "page_number": TextInput(
                attrs={
                    # "placeholder": False,
                    "inputmode": "numeric",
                    "pattern": "[0-9,]*",
                }
            ),
            "private_notes": Textarea(
                attrs={
                    # "placeholder": False,
                    "rows": 3,
                }
            ),
            "public_notes": Textarea(
                attrs={
                    # "placeholder": False,
                    "rows": 3,
                }
            ),
            "question": HiddenInput(),
        }


ResponseFormset = formset_factory(formset=ResponseFormSet, form=ResponseForm, extra=0)


class RORResponseForm(ModelForm):
    mandatory_if_response = ["evidence", "private_notes"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.authority_obj = self.initial.get("authority", None)
        self.question_obj = self.initial.get("question", None)
        self.orig = self.initial.get("original_response", None)

    def clean(self):
        cleaned_data = super().clean()

        response = cleaned_data.get("agree_with_response", None)

        if response is None:
            values = False
            for field in self.mandatory_if_response:
                val = self.cleaned_data.get(field, None)
                if val is not None and val != "":
                    values = True

            if values:
                self.add_error("agree_with_response", "This field is required")

        else:
            if response is not True:
                for field in self.mandatory_if_response:
                    value = cleaned_data.get(field, None)
                    if value is None or value == "":
                        self.add_error(field, "This field is required")

        return cleaned_data

    class Meta:
        model = Response
        fields = [
            "authority",
            "evidence",
            "id",
            "private_notes",
            "question",
            "agree_with_response",
        ]
        widgets = {
            "authority": HiddenInput(),
            "evidence": Textarea(
                attrs={
                    # "placeholder": False,
                    "rows": 3,
                },
            ),
            "id": HiddenInput(),
            "private_notes": Textarea(
                attrs={
                    # "placeholder": False,
                    "rows": 3,
                }
            ),
            "question": HiddenInput(),
        }
        labels = {
            "evidence": "Links to evidence",
        }
        help_texts = {
            "private_notes": "Please feel free to add any notes/comments you may have.",
            "evidence": "Please provide links to evidence you have met the criteria.",
        }


RORResponseFormset = formset_factory(
    formset=ResponseFormSet, form=RORResponseForm, extra=0
)
