# Generated by Django 4.2.15 on 2024-09-11 08:46

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("crowdsourcer", "0054_markingsession_default"),
    ]

    operations = [
        migrations.AddField(
            model_name="marker",
            name="send_welcome_email",
            field=models.BooleanField(default=False),
        ),
    ]
