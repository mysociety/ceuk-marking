# Generated by Django 4.2.3 on 2023-09-12 14:12

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("crowdsourcer", "0034_historicalresponse_points_response_points"),
    ]

    operations = [
        migrations.AddField(
            model_name="publicauthority",
            name="political_coalition",
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AddField(
            model_name="publicauthority",
            name="political_control",
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
    ]
