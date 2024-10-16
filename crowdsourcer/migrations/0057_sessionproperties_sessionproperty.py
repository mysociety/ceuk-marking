# Generated by Django 4.2.15 on 2024-10-07 09:38

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("crowdsourcer", "0056_assigned_created_assigned_last_update_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="SessionProperties",
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
                    "name",
                    models.CharField(help_text="Keyname in database", max_length=200),
                ),
                ("label", models.CharField(help_text="Form label", max_length=200)),
                (
                    "description",
                    models.TextField(
                        blank=True,
                        help_text="Displayed under field to describe content",
                        null=True,
                    ),
                ),
                (
                    "property_type",
                    models.CharField(
                        choices=[("text", "Text"), ("url", "URL")], max_length=200
                    ),
                ),
                ("active", models.BooleanField(default=True)),
                ("order", models.IntegerField(default=0)),
                (
                    "marking_session",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="crowdsourcer.markingsession",
                    ),
                ),
                (
                    "stage",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to="crowdsourcer.responsetype",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="SessionPropertyValues",
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
                ("value", models.TextField()),
                (
                    "authority",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to="crowdsourcer.publicauthority",
                    ),
                ),
                (
                    "property",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="crowdsourcer.sessionproperties",
                    ),
                ),
            ],
        ),
    ]
