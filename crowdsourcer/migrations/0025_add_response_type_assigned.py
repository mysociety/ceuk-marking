# Generated by Django 4.1.7 on 2023-05-04 13:20

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("crowdsourcer", "0024_add_active_response_type"),
    ]

    operations = [
        migrations.AddField(
            model_name="assigned",
            name="response_type",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                to="crowdsourcer.responsetype",
            ),
        ),
        migrations.AddField(
            model_name="historicalassigned",
            name="response_type",
            field=models.ForeignKey(
                blank=True,
                db_constraint=False,
                null=True,
                on_delete=django.db.models.deletion.DO_NOTHING,
                related_name="+",
                to="crowdsourcer.responsetype",
            ),
        ),
    ]
