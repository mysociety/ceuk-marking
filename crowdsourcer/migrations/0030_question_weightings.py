# Generated by Django 4.2.3 on 2023-07-17 09:48

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("crowdsourcer", "0029_historicalresponse_foi_answer_in_ror_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="question",
            name="weighting",
            field=models.CharField(
                choices=[("low", "Low"), ("medium", "Medium"), ("high", "High")],
                default="low",
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name="historicalresponse",
            name="foi_answer_in_ror",
            field=models.BooleanField(
                default=False,
                help_text="The council did not respond to the FOI request, but did provide the information as part of their Right of Reply response",
                verbose_name="Council responded via Right of Reply",
            ),
        ),
        migrations.AlterField(
            model_name="response",
            name="foi_answer_in_ror",
            field=models.BooleanField(
                default=False,
                help_text="The council did not respond to the FOI request, but did provide the information as part of their Right of Reply response",
                verbose_name="Council responded via Right of Reply",
            ),
        ),
    ]
