# Generated by Django 4.2.15 on 2024-11-15 14:51

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("crowdsourcer", "0058_alter_sessionproperties_options_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="SessionConfig",
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
                (
                    "config_type",
                    models.CharField(
                        choices=[("text", "Text"), ("url", "URL"), ("json", "JSON")],
                        max_length=200,
                    ),
                ),
                ("text_value", models.TextField(blank=True, null=True)),
                ("json_value", models.JSONField(blank=True, null=True)),
                (
                    "marking_session",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="crowdsourcer.markingsession",
                    ),
                ),
            ],
        ),
    ]