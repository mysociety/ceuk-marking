# Generated by Django 4.1.6 on 2023-02-22 14:05

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("crowdsourcer", "0018_publicauthority_do_not_mark"),
    ]

    operations = [
        migrations.AddField(
            model_name="publicauthority",
            name="type",
            field=models.TextField(blank=True, default="", max_length=20, null=True),
        ),
    ]
