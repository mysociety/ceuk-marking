# Generated by Django 4.2.5 on 2024-04-15 16:51

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("crowdsourcer", "0042_markingsession_active"),
    ]

    operations = [
        migrations.AlterField(
            model_name="markingsession",
            name="label",
            field=models.CharField(max_length=200, unique=True),
        ),
    ]