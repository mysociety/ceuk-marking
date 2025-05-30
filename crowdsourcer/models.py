import re

from django.contrib.auth.models import User
from django.db import models
from django.db.models import Count, OuterRef, Subquery
from django.urls import reverse

from simple_history.models import HistoricalRecords


class MarkingSession(models.Model):
    """Used to group questions and answers into sets

    To enable more than one set of questions to be stored at once.
    start_date for including/excluding authories based on their start/end date
    """

    label = models.CharField(max_length=200, unique=True)
    start_date = models.DateField()
    active = models.BooleanField(default=False)
    stage = models.ForeignKey("ResponseType", null=True, on_delete=models.SET_NULL)
    entity_name = models.TextField(max_length=200, null=True, blank=True)
    default = models.BooleanField(default=False)

    def __str__(self):
        return self.label


class SessionConfig(models.Model):
    CONFIG_TYPES = [
        ("text", "Text"),
        ("url", "URL"),
        ("json", "JSON"),
    ]
    marking_session = models.ForeignKey(MarkingSession, on_delete=models.CASCADE)
    name = models.CharField(max_length=200, help_text="Keyname in database")
    config_type = models.CharField(max_length=200, choices=CONFIG_TYPES)
    text_value = models.TextField(null=True, blank=True)
    json_value = models.JSONField(null=True, blank=True)

    @property
    def value(self):
        if self.config_type == "json":
            return self.json_value
        else:
            return self.text_value

    @classmethod
    def get_config(cls, marking_session, name):
        try:
            config = cls.objects.get(name=name, marking_session=marking_session)
            config = config.value
            return config
        except cls.DoesNotExist:
            return None


class SessionProperties(models.Model):
    """Used to define extra properties that can be added as part of marking"""

    PROPERTY_TYPES = [
        ("text", "Text"),
        ("url", "URL"),
    ]

    marking_session = models.ForeignKey(MarkingSession, on_delete=models.CASCADE)
    stage = models.ForeignKey("ResponseType", null=True, on_delete=models.SET_NULL)
    name = models.CharField(max_length=200, help_text="Keyname in database")
    label = models.CharField(max_length=200, help_text="Form label")
    description = models.TextField(
        help_text="Displayed under field to describe content", null=True, blank=True
    )
    property_type = models.CharField(max_length=200, choices=PROPERTY_TYPES)
    active = models.BooleanField(default=True)
    order = models.IntegerField(default=0)

    def __str__(self):
        return f"{self.label} ({self.marking_session}, {self.stage})"

    class Meta:
        verbose_name_plural = "Session Properties"


class SessionPropertyValues(models.Model):
    """For storing extra session properties"""

    authority = models.ForeignKey(
        "PublicAuthority", null=True, on_delete=models.SET_NULL
    )
    property = models.ForeignKey(SessionProperties, on_delete=models.CASCADE)
    value = models.TextField()

    def __str__(self):
        return f"{self.property} {self.authority} - {self.value}"

    class Meta:
        verbose_name_plural = "Session Property Values"


class Section(models.Model):
    """Used to group questions with a similar theme"""

    title = models.CharField(max_length=200)
    marking_session = models.ForeignKey(MarkingSession, on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.title} ({self.marking_session.label})"


class QuestionGroup(models.Model):
    """Determines which questions are relevant for an authority

    Not all questions in a section are relevant to all authorities so questions
    and authorities belong to QuestionGroups
    """

    description = models.TextField(max_length=200)
    marking_session = models.ManyToManyField(MarkingSession)

    def __str__(self):
        return self.description


class Question(models.Model):
    MARKING_TYPES = [
        ("foi", "FOI"),
        ("national_data", "National Data"),
        ("volunteer", "Volunteer Research"),
        ("national_volunteer", "National Data and Volunteer Research"),
    ]
    QUESTION_TYPES = [
        ("yes_no", "Yes/No"),
        ("foi", "FOI"),
        ("national_data", "National Data"),
        ("select_one", "Select One"),
        ("tiered", "Tiered Answer"),
        ("multiple_choice", "Multiple Choice"),
        ("negative", "Negatively Marked"),
    ]
    WEIGHTINGS = [
        ("low", "Low"),
        ("medium", "Medium"),
        ("high", "High"),
        ("unweighted", "Unweighted"),
    ]
    VOLUNTEER_TYPES = ["volunteer", "national_volunteer"]
    number = models.IntegerField(blank=True, null=True)
    number_part = models.CharField(max_length=4, blank=True, null=True)
    description = models.TextField()
    criteria = models.TextField(blank=True, null=True)
    section = models.ForeignKey(Section, on_delete=models.CASCADE)
    questiongroup = models.ManyToManyField(QuestionGroup, blank=True)
    clarifications = models.TextField(blank=True, null=True)
    topic = models.CharField(max_length=200, blank=True, null=True)
    how_marked = models.CharField(
        max_length=30, default="volunteer", choices=MARKING_TYPES
    )
    question_type = models.CharField(
        max_length=30, default="yes_no", choices=QUESTION_TYPES
    )
    weighting = models.CharField(max_length=20, default="low", choices=WEIGHTINGS)
    previous_question = models.ForeignKey(
        "Question", blank=True, null=True, on_delete=models.SET_NULL
    )
    read_only = models.BooleanField(default=False)
    created = models.DateTimeField(auto_now_add=True)
    last_update = models.DateTimeField(auto_now=True)

    @property
    def number_and_part(self):
        if self.number_part is not None:
            return f"{self.number}{self.number_part}"
        return f"{self.number}"

    def __str__(self):
        return f"{self.number_and_part}. {self.section} - {self.description}"

    def options(self):
        return Option.objects.filter(question=self).order_by("ordering", "score")

    @classmethod
    def get_question_from_number_and_part(cls, number_and_part, section, session):
        q_parts = re.search(r"(\d+)([a-z]?)", number_and_part).groups()
        args = {
            "number": q_parts[0],
            "section__title": section,
            "section__marking_session__label": session,
        }
        if len(q_parts) == 2 and q_parts[1] != "":
            args["number_part"] = q_parts[1]

        try:
            q = cls.objects.get(**args)
        except cls.DoesNotExist:
            return None

        return q


class AuthorityData(models.Model):
    authority = models.ForeignKey("PublicAuthority", on_delete=models.CASCADE)
    data_name = models.CharField(max_length=200)
    data_value = models.TextField()

    class Meta:
        indexes = [
            models.Index(fields=["authority", "data_name"]),
        ]


class PublicAuthority(models.Model):
    COUNTRIES = [
        ("england", "England"),
        ("northern ireland", "Northern Ireland"),
        ("scotland", "Scotland"),
        ("wales", "Wales"),
    ]

    unique_id = models.CharField(max_length=100, unique=True)
    name = models.TextField(max_length=300)
    website = models.URLField(null=True)
    questiongroup = models.ForeignKey(QuestionGroup, on_delete=models.CASCADE)
    do_not_mark = models.BooleanField(default=False)
    type = models.TextField(max_length=20, default="", blank=True, null=True)
    country = models.CharField(max_length=20, blank=True, null=True, choices=COUNTRIES)
    political_control = models.CharField(max_length=100, blank=True, null=True)
    political_coalition = models.CharField(max_length=100, blank=True, null=True)
    marking_session = models.ManyToManyField(MarkingSession)

    def __str__(self):
        name = self.name
        if self.do_not_mark:
            name = f"{name} (DO NOT MARK)"

        return name

    @classmethod
    def maps(cls):
        gss_map = {}
        groups = {}
        countries = {}
        types = {}
        control = {}

        for a in cls.objects.filter(do_not_mark=False).all():
            gss_map[a.name] = a.unique_id
            groups[a.name] = a.questiongroup.description
            countries[a.name] = a.country
            types[a.name] = a.type
            control[a.name] = a.political_control

        return gss_map, groups, countries, types, control

    @classmethod
    def response_counts(
        cls,
        questions,
        section,
        user,
        marking_session,
        assigned=None,
        response_type=None,
        question_types=None,
        right_of_reply=False,
        ignore_question_list=False,
    ):
        if response_type is None:
            response_type = ResponseType.objects.get(type="First Mark")

        if question_types is None:
            question_types = Question.VOLUNTEER_TYPES

        stage_name = ""
        if right_of_reply:
            stage_name = "Right of Reply"
        null_responses = Response.null_responses(stage_name=stage_name)

        authorities = cls.objects.filter(
            marking_session=marking_session, questiongroup__question__in=questions
        ).annotate(
            num_questions=Subquery(
                Question.objects.filter(
                    id__in=questions,
                    questiongroup=OuterRef("questiongroup"),
                    section__title=section,
                    section__marking_session=marking_session,
                    how_marked__in=question_types,
                )
                .values("questiongroup")
                .annotate(num_questions=Count("pk"))
                .values("num_questions")
            ),
        )

        args = {
            "question__in": questions,
        }
        if ignore_question_list:
            args = {
                "question__questiongroup": OuterRef("questiongroup"),
                "question__section__title": section,
                "question__section__marking_session": marking_session,
            }
        if question_types:
            args["question__how_marked__in"] = question_types

        authorities = authorities.annotate(
            num_responses=Subquery(
                Response.objects.filter(
                    authority=OuterRef("pk"),
                    response_type=response_type,
                    **args,
                )
                .exclude(id__in=null_responses)
                .values("authority")
                .annotate(response_count=Count("question_id", distinct=True))
                .values("response_count")
            ),
        )

        if assigned is not None:
            authorities = authorities.filter(id__in=assigned)

        return authorities

    def get_data(self, data_name):
        try:
            data = AuthorityData.objects.get(authority=self, data_name=data_name)
            return data.data_value
        except AuthorityData.DoesNotExist:
            return None

    class Meta:
        verbose_name_plural = "authorities"


class Option(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    score = models.IntegerField()
    description = models.TextField(max_length=200)
    ordering = models.IntegerField(blank=True, null=True)
    created = models.DateTimeField(auto_now_add=True)
    last_update = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.description

    class Meta:
        ordering = ["ordering", "score"]


class ResponseType(models.Model):
    type = models.TextField(max_length=200)
    priority = models.IntegerField()
    active = models.BooleanField(default=False)

    @classmethod
    def choices(cls):
        choices = cls.objects.values_list("pk", "type")
        return choices

    def __str__(self):
        return self.type


class Response(models.Model):
    authority = models.ForeignKey(PublicAuthority, on_delete=models.CASCADE)
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    option = models.ForeignKey(
        Option, on_delete=models.CASCADE, blank=True, null=True, verbose_name="Answer"
    )
    multi_option = models.ManyToManyField(
        Option, blank=True, verbose_name="Answer", related_name="multi_option"
    )
    response_type = models.ForeignKey(ResponseType, on_delete=models.CASCADE, null=True)
    public_notes = models.TextField(
        verbose_name="Link to evidence (links only to webpages or online documents)",
        blank=True,
        null=True,
    )
    page_number = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name="Page Number",
        help_text="Please directly copy the page number from the document where you have found the evidence.",
    )
    evidence = models.TextField(
        blank=True,
        null=True,
        verbose_name="Evidence of criteria met",
        help_text="Please directly copy any evidence you have found to meet the criteria.",
    )
    private_notes = models.TextField(
        blank=True,
        verbose_name="Additional Notes",
        help_text="Please feel free to add any notes/comments you may have. These will not be made public but will be sent to the Council in the Right of Reply.",
    )
    agree_with_response = models.BooleanField(null=True, blank=True)
    foi_answer_in_ror = models.BooleanField(
        default=False,
        verbose_name="Council responded via Right of Reply",
        help_text="The council did not respond to the FOI request, but did provide the information as part of their Right of Reply response",
    )
    revision_type = models.CharField(max_length=200, blank=True, null=True)
    revision_notes = models.TextField(blank=True, null=True)
    created = models.DateTimeField(auto_now_add=True)
    last_update = models.DateTimeField(auto_now=True)
    history = HistoricalRecords()

    points = models.FloatField(
        blank=True, null=True, help_text="overide marks for this response"
    )

    def get_absolute_url(self):
        return reverse(
            "authority_question_edit",
            kwargs={
                "name": self.authority.name,
                "section_title": self.question.section.title,
                "number": self.question.number,
            },
        )

    @property
    def evidence_links(self):
        text = self.public_notes
        if text is None:
            return []
        links = re.findall(r"((?:https?://|www\.)[^ \r\n]*)", text)
        return links

    @classmethod
    def null_responses(cls, stage_name=""):
        if stage_name == "Right of Reply":
            return cls.objects.filter(agree_with_response__isnull=True)

        return cls.objects.filter(option__isnull=True, multi_option__isnull=True)

    @classmethod
    def get_response_for_question(
        cls,
        session=None,
        section=None,
        question_number=None,
        question_part=None,
        response_type=None,
        authority=None,
    ):
        args = {
            "question__section__marking_session__label": session,
            "question__section__title": section,
            "question__number": question_number,
            "response_type__type": response_type,
            "authority__name": authority,
        }
        if question_part:
            args["question__number_part"] = question_part

        try:
            r = cls.objects.get(**args)
        except Response.DoesNotExist:
            r = None

        return r


class Assigned(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    active = models.BooleanField(default=True)
    section = models.ForeignKey(
        Section, on_delete=models.CASCADE, null=True, blank=True
    )
    authority = models.ForeignKey(
        PublicAuthority, on_delete=models.CASCADE, null=True, blank=True
    )
    question = models.ForeignKey(
        Question, on_delete=models.CASCADE, null=True, blank=True
    )
    response_type = models.ForeignKey(
        ResponseType, on_delete=models.CASCADE, null=True, blank=True
    )
    marking_session = models.ForeignKey(MarkingSession, on_delete=models.CASCADE)
    created = models.DateTimeField(auto_now_add=True)
    last_update = models.DateTimeField(auto_now=True)
    history = HistoricalRecords()

    def __str__(self):
        parts = [self.user.email, self.marking_session.label]
        if self.authority is not None:
            parts.append(self.authority.name)
        if self.section is not None:
            parts.append(self.section.title)
        if self.response_type is not None:
            parts.append(self.response_type.type)

        return ", ".join(parts)

    @classmethod
    def is_user_assigned(cls, user, **kwargs):
        if user.is_superuser:
            return True

        if user.is_anonymous:
            return False

        q = cls.objects.filter(user=user, active=True)
        q_all_stage = None

        if kwargs.get("section", None) is not None:
            q = q.filter(section__title=kwargs["section"])
            q_section = q.filter(section__title=kwargs["section"], authority=None)
        if kwargs.get("authority", None) is not None:
            q = q.filter(authority__name=kwargs["authority"])
        if kwargs.get("marking_session", None) is not None:
            q = q.filter(marking_session=kwargs["marking_session"])
        if kwargs.get("current_stage", None) is not None:
            q = q.filter(response_type=kwargs["current_stage"])
            q_all_stage = cls.objects.filter(
                user=user,
                active=True,
                section__isnull=True,
                authority__isnull=True,
                response_type=kwargs["current_stage"],
            )

        return (
            q.exists()
            or q_section.exists()
            or (q_all_stage is not None and q_all_stage.exists())
        )

    class Meta:
        verbose_name = "assignment"
        verbose_name_plural = "assignments"
        unique_together = [["section", "authority", "response_type"]]


class Marker(models.Model):
    """Addition user properties

    One to One for a users. Stores details that control access to questions
    and authorities.
    """

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    response_type = models.ForeignKey(
        ResponseType,
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        verbose_name="Response Type",
    )
    authority = models.ForeignKey(
        PublicAuthority, blank=True, null=True, on_delete=models.SET_NULL
    )
    marking_session = models.ManyToManyField(MarkingSession, blank=True)
    send_welcome_email = models.BooleanField(default=False)
    created = models.DateTimeField(auto_now_add=True)
    last_update = models.DateTimeField(auto_now=True)

    class Meta:
        permissions = [
            ("can_view_all_responses", "Can view all responses"),
            ("can_view_progress", "Can view progress"),
            ("can_view_stats", "Can view stats"),
            ("can_manage_users", "Can manage users"),
        ]
