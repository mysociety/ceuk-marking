# Generated by Django 4.1.4 on 2023-01-18 17:39

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("crowdsourcer", "0009_add_response_history"),
    ]

    operations = [
        migrations.AlterField(
            model_name="historicalresponse",
            name="option",
            field=models.ForeignKey(
                blank=True,
                db_constraint=False,
                null=True,
                on_delete=django.db.models.deletion.DO_NOTHING,
                related_name="+",
                to="crowdsourcer.option",
                verbose_name="Answer",
            ),
        ),
        migrations.AlterField(
            model_name="historicalresponse",
            name="public_notes",
            field=models.TextField(
                blank=True,
                null=True,
                verbose_name="Link to evidence (links only to webpages or online documents)",
            ),
        ),
        migrations.AlterField(
            model_name="response",
            name="option",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                to="crowdsourcer.option",
                verbose_name="Answer",
            ),
        ),
        migrations.AlterField(
            model_name="response",
            name="public_notes",
            field=models.TextField(
                blank=True,
                null=True,
                verbose_name="Link to evidence (links only to webpages or online documents)",
            ),
        ),
    ]