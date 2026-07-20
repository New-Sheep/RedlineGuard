# Generated for E2 starter playbook + labels polish

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("review", "0006_semantic_compare"),
    ]

    operations = [
        migrations.AddField(
            model_name="playbookimport",
            name="starter_manifest",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AlterField(
            model_name="playbookimport",
            name="source",
            field=models.CharField(
                choices=[
                    ("upload", "Upload"),
                    ("sample", "Sample"),
                    ("starter", "Starter from past contracts"),
                ],
                max_length=16,
            ),
        ),
        migrations.AlterField(
            model_name="playbookimport",
            name="progress_step",
            field=models.CharField(
                blank=True,
                choices=[
                    ("queued", "Queued"),
                    ("reading", "Reading source"),
                    ("security", "Security check"),
                    ("proposing", "Proposing rules"),
                    ("done", "Done"),
                ],
                default="queued",
                max_length=16,
            ),
        ),
    ]
