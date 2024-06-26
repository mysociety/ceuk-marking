# Generated by Django 4.2.11 on 2024-06-26 10:56

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("crowdsourcer", "0052_publicauthority_marking_session"),
    ]

    operations = [
        migrations.AlterField(
            model_name="marker",
            name="marking_session",
            field=models.ManyToManyField(blank=True, to="crowdsourcer.markingsession"),
        ),
        migrations.AlterField(
            model_name="question",
            name="previous_question",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to="crowdsourcer.question",
            ),
        ),
        migrations.AlterField(
            model_name="question",
            name="questiongroup",
            field=models.ManyToManyField(blank=True, to="crowdsourcer.questiongroup"),
        ),
    ]
