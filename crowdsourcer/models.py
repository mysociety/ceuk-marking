from django.contrib.auth.models import User
from django.db import models
from django.db.models import Count, OuterRef, Subquery
from django.urls import reverse

from simple_history.models import HistoricalRecords


class Section(models.Model):
    title = models.CharField(max_length=200)

    def __str__(self):
        return self.title


class QuestionGroup(models.Model):
    description = models.TextField(max_length=200)

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
    ]
    VOLUNTEER_TYPES = ["volunteer", "national_volunteer"]
    number = models.IntegerField(blank=True, null=True)
    number_part = models.CharField(max_length=4, blank=True, null=True)
    description = models.TextField()
    criteria = models.TextField(blank=True, null=True)
    section = models.ForeignKey(Section, on_delete=models.CASCADE)
    questiongroup = models.ManyToManyField(QuestionGroup)
    clarifications = models.TextField(blank=True, null=True)
    topic = models.CharField(max_length=200, blank=True, null=True)
    how_marked = models.CharField(
        max_length=30, default="volunteer", choices=MARKING_TYPES
    )
    question_type = models.CharField(
        max_length=30, default="yes_no", choices=QUESTION_TYPES
    )

    @property
    def number_and_part(self):
        if self.number_part is not None:
            return f"{self.number}{self.number_part}"
        return f"{self.number}"

    def __str__(self):
        return f"{self.number_and_part}. {self.description}"

    def options(self):
        return Option.objects.filter(question=self).order_by("ordering", "score")


class PublicAuthority(models.Model):
    unique_id = models.CharField(max_length=100, unique=True)
    name = models.TextField(max_length=300)
    website = models.URLField(null=True)
    questiongroup = models.ForeignKey(QuestionGroup, on_delete=models.CASCADE)
    do_not_mark = models.BooleanField(default=False)
    type = models.TextField(max_length=20, default="", blank=True, null=True)

    def __str__(self):
        name = self.name
        if self.do_not_mark:
            name = f"{name} (DO NOT MARK)"

        return name

    @classmethod
    def response_counts(
        cls,
        questions,
        section,
        user,
        assigned=None,
        response_type=None,
        question_types=None,
    ):
        if response_type is None:
            response_type = ResponseType.objects.get(type="First Mark")

        if question_types is None:
            question_types = Question.VOLUNTEER_TYPES

        authorities = cls.objects.filter(
            questiongroup__question__in=questions
        ).annotate(
            num_questions=Subquery(
                Question.objects.filter(
                    questiongroup=OuterRef("questiongroup"),
                    section__title=section,
                    how_marked__in=question_types,
                )
                .values("questiongroup")
                .annotate(num_questions=Count("pk"))
                .values("num_questions")
            ),
        )

        authorities = authorities.annotate(
            num_responses=Subquery(
                Response.objects.filter(
                    authority=OuterRef("pk"),
                    question__in=questions,
                    response_type=response_type,
                )
                .values("authority")
                .annotate(response_count=Count("pk"))
                .values("response_count")
            )
        )

        if assigned is not None:
            authorities = authorities.filter(id__in=assigned)

        return authorities

    class Meta:
        verbose_name_plural = "authorities"


class Option(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    score = models.IntegerField()
    description = models.TextField(max_length=200)
    ordering = models.IntegerField(blank=True, null=True)

    def __str__(self):
        return self.description

    class Meta:
        ordering = ["ordering", "score"]


class ResponseType(models.Model):
    type = models.TextField(max_length=200)
    priority = models.IntegerField()
    active = models.BooleanField(default=False)

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
        verbose_name="Responded to in Right of Reply",
        help_text="The council did not respond to the FOI request, but did provide the information as part of their Right of Reply response",
    )
    revision_type = models.CharField(max_length=200, blank=True, null=True)
    revision_notes = models.TextField(blank=True, null=True)
    created = models.DateTimeField(auto_now_add=True)
    last_update = models.DateTimeField(auto_now=True)
    history = HistoricalRecords()

    def get_absolute_url(self):
        return reverse(
            "authority_question_edit",
            kwargs={
                "name": self.authority.name,
                "section_title": self.question.section.title,
                "number": self.question.number,
            },
        )


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
    history = HistoricalRecords()

    @classmethod
    def is_user_assigned(cls, user, **kwargs):
        if user.is_superuser:
            return True

        if user.is_anonymous:
            return False

        q = cls.objects.filter(user=user)

        if kwargs.get("section", None) is not None:
            q = q.filter(section__title=kwargs["section"])
            q_section = q.filter(section__title=kwargs["section"], authority=None)
        if kwargs.get("authority", None) is not None:
            q = q.filter(authority__name=kwargs["authority"])
        if kwargs.get("current_stage", None) is not None:
            q = q.filter(response_type=kwargs["current_stage"])

        return q.exists() or q_section.exists()

    class Meta:
        verbose_name = "assignment"
        verbose_name_plural = "assignments"
        unique_together = [["section", "authority", "response_type"]]


class Marker(models.Model):
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
