# Generated by Django 4.2.15 on 2024-08-15 13:15

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("crowdsourcer", "0053_alter_marker_marking_session_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="markingsession",
            name="default",
            field=models.BooleanField(default=False),
        ),
    ]
