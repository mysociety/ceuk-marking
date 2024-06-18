from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.validators import validate_comma_separated_integer_list
from django.db.models.query import QuerySet
from django.forms import (
    BaseFormSet,
    BooleanField,
    CharField,
    CheckboxSelectMultiple,
    ChoiceField,
    FileField,
    Form,
    HiddenInput,
    IntegerField,
    ModelForm,
    Select,
    Textarea,
    TextInput,
    formset_factory,
    inlineformset_factory,
)

import pandas as pd

from crowdsourcer.models import (
    Assigned,
    Marker,
    MarkingSession,
    Option,
    PublicAuthority,
    Response,
    ResponseType,
    Section,
)
from crowdsourcer.volunteers import check_bulk_assignments


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


class AuditResponseForm(ModelForm):
    mandatory_if_no = ["private_notes"]
    mandatory_if_response = ["public_notes", "page_number", "evidence", "private_notes"]
    mandatory_if_national = []

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
        self.orig = self.initial.get("original_response", None)
        self.ror = self.initial.get("ror_response", None)

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
            if self.question_obj.how_marked == "national_data":
                mandatory = self.mandatory_if_national
            elif str(response) in ["No", "None"]:
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
            "foi_answer_in_ror",
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
        labels = {
            "evidence": "Evidence of criteria met",
        }


AuditResponseFormset = formset_factory(
    formset=ResponseFormSet, form=AuditResponseForm, extra=0
)


class UserForm(ModelForm):
    class Meta:
        model = User
        fields = [
            "first_name",
            "last_name",
            "email",
            "username",
            "is_active",
        ]


class MarkerForm(ModelForm):
    def __init__(self, session=None, **kwargs):
        super().__init__(**kwargs)
        if session is not None:
            self.fields["authority"].queryset = PublicAuthority.objects.filter(
                questiongroup__marking_session=session
            )

    class Meta:
        model = Marker
        fields = ["response_type", "authority"]


MarkerFormset = inlineformset_factory(User, Marker, form=MarkerForm, can_delete=False)


class VolunteerAssignentForm(ModelForm):
    def __init__(self, session=None, **kwargs):
        super().__init__(**kwargs)
        if session is not None:
            self.fields["authority"].queryset = PublicAuthority.objects.filter(
                questiongroup__marking_session=session,
            ).order_by("name")
            self.fields["section"].queryset = Section.objects.filter(
                marking_session=session
            )

            if self.fields["marking_session"].initial is None:
                self.fields["marking_session"].initial = session

        if self.instance.section is not None:
            assigned_authorities = (
                Assigned.objects.filter(
                    response_type=self.instance.response_type,
                    marking_session=session,
                    section=self.instance.section,
                )
                .exclude(id=self.instance.id)
                .values_list("authority_id", flat=True)
            )
            self.fields["authority"].queryset = (
                self.fields["authority"]
                .queryset.exclude(id__in=assigned_authorities)
                .order_by("name")
            )

    class Meta:
        model = Assigned
        fields = ["section", "response_type", "authority", "marking_session", "active"]
        widgets = {
            "marking_session": HiddenInput(
                attrs={"class": "form-select field_session"}
            ),
            "section": Select(attrs={"class": "form-select field_section"}),
            "response_type": Select(attrs={"class": "form-select field_rt"}),
            "authority": Select(attrs={"class": "form-select field_authority"}),
        }


VolunteerAssignmentFormset = inlineformset_factory(
    User, Assigned, form=VolunteerAssignentForm, extra=1
)


class VolunteerBulkAssignForm(Form):
    volunteer_list = FileField(
        required=True,
        label="Volunteer list (Excel file)",
        help_text="Volunteers will be loaded from sheet 'Volunteers' using column headers 'First Name', 'Last Name', 'Email', 'Assigned Section'",
    )
    num_assignments = IntegerField(
        required=True,
        label="Number of assignments per volunteer",
    )
    response_type = ChoiceField(required=True, choices=[])
    session = CharField(required=True, widget=HiddenInput)
    always_assign = BooleanField(
        required=False, help_text="Override checks and assign as much as possible"
    )

    def __init__(self, response_choices, **kwargs):
        super().__init__(**kwargs)
        self.fields["response_type"].choices = response_choices

    def clean(self):
        data = self.cleaned_data.get("volunteer_list")

        try:
            df = pd.read_excel(
                data,
                usecols=[
                    "First Name",
                    "Last Name",
                    "Email",
                    "Council Area",
                    "Assigned Section",
                ],
                sheet_name="Volunteers",
            )
        except ValueError as v:
            raise ValidationError(f"Problem processing excel file: {v}")

        rt = ResponseType.objects.get(type=self.cleaned_data["response_type"])
        ms = MarkingSession.objects.get(label=self.cleaned_data["session"])
        num_assignments = self.cleaned_data.get("num_assignments")

        errors = check_bulk_assignments(
            df, rt, ms, num_assignments, self.cleaned_data["always_assign"]
        )

        if errors:
            errors = [ValidationError(e) for e in errors]
            raise ValidationError(errors)

        self.volunteer_df = df
