# Generated by Django 4.2.15 on 2024-10-16 09:16

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("crowdsourcer", "0057_sessionproperties_sessionproperty"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="sessionproperties",
            options={"verbose_name_plural": "Session Properties"},
        ),
        migrations.AlterModelOptions(
            name="sessionpropertyvalues",
            options={"verbose_name_plural": "Session Property Values"},
        ),
    ]
