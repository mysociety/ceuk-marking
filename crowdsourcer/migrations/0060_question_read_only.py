# Generated by Django 4.2.16 on 2024-11-21 15:30

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("crowdsourcer", "0059_sessionconfig"),
    ]

    operations = [
        migrations.AddField(
            model_name="question",
            name="read_only",
            field=models.BooleanField(default=False),
        ),
    ]