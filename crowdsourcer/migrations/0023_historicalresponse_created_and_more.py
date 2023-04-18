# Generated by Django 4.1.6 on 2023-03-15 17:10

from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ("crowdsourcer", "0022_marker"),
    ]

    operations = [
        migrations.AddField(
            model_name="historicalresponse",
            name="created",
            field=models.DateTimeField(
                blank=True, default=django.utils.timezone.now, editable=False
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="historicalresponse",
            name="last_update",
            field=models.DateTimeField(
                blank=True, default=django.utils.timezone.now, editable=False
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="response",
            name="created",
            field=models.DateTimeField(
                auto_now_add=True, default=django.utils.timezone.now
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="response",
            name="last_update",
            field=models.DateTimeField(auto_now=True),
        ),
    ]