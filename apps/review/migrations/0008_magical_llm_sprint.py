"""Magical sprint fields: proposal source, plain_english, copilot, coverage gaps."""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("review", "0007_playbook_starter"),
    ]

    operations = [
        migrations.AddField(
            model_name="playbookimport",
            name="proposal_source",
            field=models.CharField(blank=True, default="fake", max_length=32),
        ),
        migrations.AddField(
            model_name="playbookimport",
            name="proposal_model",
            field=models.CharField(blank=True, default="", max_length=128),
        ),
        migrations.AddField(
            model_name="reviewrun",
            name="coverage_gaps",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="finding",
            name="plain_english",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="draft",
            name="provider_label",
            field=models.CharField(blank=True, default="", max_length=32),
        ),
        migrations.AddField(
            model_name="draft",
            name="copilot_json",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="draft",
            name="memory_explain",
            field=models.TextField(blank=True, default=""),
        ),
    ]
