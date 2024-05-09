# Generated by Django 4.2.5 on 2024-04-23 15:23

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("crowdsourcer", "0044_marker_marking_session"),
    ]

    operations = [
        migrations.AddField(
            model_name="markingsession",
            name="stage",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to="crowdsourcer.responsetype",
            ),
        ),
    ]