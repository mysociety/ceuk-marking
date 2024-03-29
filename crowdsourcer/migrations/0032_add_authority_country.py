# Generated by Django 4.2.3 on 2023-08-02 13:26

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("crowdsourcer", "0031_add_unweighted"),
    ]

    operations = [
        migrations.AddField(
            model_name="publicauthority",
            name="country",
            field=models.CharField(
                blank=True,
                choices=[
                    ("england", "England"),
                    ("northern ireland", "Northern Ireland"),
                    ("scotland", "Scotland"),
                    ("wales", "Wales"),
                ],
                max_length=20,
                null=True,
            ),
        ),
    ]
