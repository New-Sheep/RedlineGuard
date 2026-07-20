# Generated manually for semantic compare sprint

from django.db import migrations, models


def _default_sources():
    return ["rule"]


class Migration(migrations.Migration):

    dependencies = [
        ("review", "0005_playbook_import_progress"),
    ]

    operations = [
        migrations.AddField(
            model_name="reviewrun",
            name="score_breakdown",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="finding",
            name="sources",
            field=models.JSONField(blank=True, default=_default_sources),
        ),
        migrations.AddField(
            model_name="finding",
            name="confidence",
            field=models.FloatField(default=1.0),
        ),
        migrations.AddField(
            model_name="finding",
            name="match_distance",
            field=models.FloatField(blank=True, null=True),
        ),
    ]
