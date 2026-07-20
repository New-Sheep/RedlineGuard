# Generated for lawyer wishlist sprints

from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):
    dependencies = [
        ("contracts", "0003_sprint4_progress_llm"),
        ("decisions", "0004_memory_meta"),
    ]

    operations = [
        migrations.AddField(
            model_name="decision",
            name="superseded",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="decision",
            name="superseded_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="decision",
            name="action",
            field=models.CharField(
                choices=[
                    ("accept", "Accept"),
                    ("edit", "Edit"),
                    ("reject", "Reject"),
                    ("override", "Override & accept as-is"),
                    ("false_positive", "Report false positive"),
                ],
                max_length=16,
            ),
        ),
        migrations.CreateModel(
            name="AuditEvent",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "kind",
                    models.CharField(
                        choices=[
                            ("activate", "Playbook activate"),
                            ("restore", "Playbook restore"),
                            ("override", "Override"),
                            ("revoke_override", "Revoke override"),
                            ("decision", "Decision"),
                            ("undo", "Undo decision"),
                            ("redo", "Redo decision"),
                            ("false_positive", "False positive"),
                            ("security_override", "Security override"),
                        ],
                        max_length=32,
                    ),
                ),
                ("summary", models.CharField(blank=True, default="", max_length=512)),
                ("payload", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "contract",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="audit_events",
                        to="contracts.contract",
                    ),
                ),
                (
                    "decision",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="audit_events",
                        to="decisions.decision",
                    ),
                ),
            ],
            options={"ordering": ["-created_at"]},
        ),
    ]
