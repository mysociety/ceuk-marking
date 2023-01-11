from django.contrib.auth.models import User
from django.db import models
from django.db.models import Count, OuterRef, Subquery
from django.urls import reverse


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
    criteria = models.TextField()
    section = models.ForeignKey(Section, on_delete=models.CASCADE)
    questiongroup = models.ManyToManyField(QuestionGroup)
    how_marked = models.CharField(
        max_length=30, default="volunteer", choices=MARKING_TYPES
    )
    question_type = models.CharField(
        max_length=30, default="yes_no", choices=QUESTION_TYPES
    )

    def __str__(self):
        return self.description

    def options(self):
        return Option.objects.filter(question=self).order_by("score")


class PublicAuthority(models.Model):
    unique_id = models.CharField(max_length=100, unique=True)
    name = models.TextField(max_length=300)
    questiongroup = models.ForeignKey(QuestionGroup, on_delete=models.CASCADE)

    def __str__(self):
        return self.name

    @classmethod
    def response_counts(cls, questions, section, user, assigned=None):
        authorities = cls.objects.filter(
            questiongroup__question__in=questions
        ).annotate(
            num_questions=Subquery(
                Question.objects.filter(
                    questiongroup=OuterRef("questiongroup"),
                    section__title=section,
                    how_marked__in=Question.VOLUNTEER_TYPES,
                )
                .values("questiongroup")
                .annotate(num_questions=Count("pk"))
                .values("num_questions")
            ),
        )

        if user.is_superuser:
            authorities = authorities.annotate(
                num_responses=Subquery(
                    Response.objects.filter(
                        authority=OuterRef("pk"),
                        question__in=questions,
                    )
                    .values("authority")
                    .annotate(response_count=Count("pk"))
                    .values("response_count")
                )
            )
        else:
            authorities = authorities.annotate(
                num_responses=Subquery(
                    Response.objects.filter(
                        user=user,
                        authority=OuterRef("pk"),
                        question__in=questions,
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

    def __str__(self):
        return self.description


class ResponseType(models.Model):
    type = models.TextField(max_length=200)
    priority = models.IntegerField()

    def __str__(self):
        return self.type


class Response(models.Model):
    authority = models.ForeignKey(PublicAuthority, on_delete=models.CASCADE)
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    option = models.ForeignKey(Option, on_delete=models.CASCADE, null=True)
    response_type = models.ForeignKey(ResponseType, on_delete=models.CASCADE, null=True)
    public_notes = models.TextField()
    private_notes = models.TextField()
    revision_type = models.CharField(max_length=200, blank=True, null=True)
    revision_notes = models.TextField(blank=True, null=True)

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
    section = models.ForeignKey(
        Section, on_delete=models.CASCADE, null=True, blank=True
    )
    authority = models.ForeignKey(
        PublicAuthority, on_delete=models.CASCADE, null=True, blank=True
    )
    question = models.ForeignKey(
        Question, on_delete=models.CASCADE, null=True, blank=True
    )

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

        return q.exists() or q_section.exists()

    class Meta:
        verbose_name = "assignment"
        verbose_name_plural = "assignments"
