# Generated by Django 4.1.4 on 2022-12-19 16:12

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Option",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("score", models.IntegerField()),
                ("description", models.TextField(max_length=200)),
            ],
        ),
        migrations.CreateModel(
            name="PublicAuthority",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("unique_id", models.CharField(max_length=100, unique=True)),
                ("name", models.TextField(max_length=300)),
            ],
            options={
                "verbose_name_plural": "authorities",
            },
        ),
        migrations.CreateModel(
            name="Question",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("description", models.TextField()),
                ("criteria", models.TextField()),
            ],
        ),
        migrations.CreateModel(
            name="QuestionGroup",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("description", models.TextField(max_length=200)),
            ],
        ),
        migrations.CreateModel(
            name="ResponseType",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("type", models.TextField(max_length=200)),
                ("priority", models.IntegerField()),
            ],
        ),
        migrations.CreateModel(
            name="Section",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("title", models.CharField(max_length=200)),
            ],
        ),
        migrations.CreateModel(
            name="Response",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("public_notes", models.TextField()),
                ("private_notes", models.TextField()),
                (
                    "revision_type",
                    models.CharField(blank=True, max_length=200, null=True),
                ),
                ("revision_notes", models.TextField(blank=True, null=True)),
                (
                    "authority",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="crowdsourcer.publicauthority",
                    ),
                ),
                (
                    "option",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        to="crowdsourcer.option",
                    ),
                ),
                (
                    "question",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="crowdsourcer.question",
                    ),
                ),
                (
                    "response_type",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        to="crowdsourcer.responsetype",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
        migrations.AddField(
            model_name="question",
            name="questiongroup",
            field=models.ManyToManyField(to="crowdsourcer.questiongroup"),
        ),
        migrations.AddField(
            model_name="question",
            name="section",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE, to="crowdsourcer.section"
            ),
        ),
        migrations.AddField(
            model_name="publicauthority",
            name="questiongroup",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                to="crowdsourcer.questiongroup",
            ),
        ),
        migrations.AddField(
            model_name="option",
            name="question",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE, to="crowdsourcer.question"
            ),
        ),
        migrations.CreateModel(
            name="Assigned",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "authority",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        to="crowdsourcer.publicauthority",
                    ),
                ),
                (
                    "question",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        to="crowdsourcer.question",
                    ),
                ),
                (
                    "section",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        to="crowdsourcer.section",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "assignment",
                "verbose_name_plural": "assignments",
            },
        ),
    ]
