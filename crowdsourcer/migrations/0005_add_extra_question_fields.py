# Generated by Django 4.1.4 on 2023-01-16 17:55

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("crowdsourcer", "0004_add_how_question_marked"),
    ]

    operations = [
        migrations.AddField(
            model_name="question",
            name="clarifications",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="question",
            name="topic",
            field=models.CharField(blank=True, max_length=200, null=True),
        ),
        migrations.AlterField(
            model_name="question",
            name="criteria",
            field=models.TextField(blank=True, null=True),
        ),
    ]