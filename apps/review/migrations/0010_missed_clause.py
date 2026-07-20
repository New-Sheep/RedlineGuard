# Generated for F22 missed clause

from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):
    dependencies = [
        ("contracts", "0003_sprint4_progress_llm"),
        ("review", "0009_agent_assist"),
    ]

    operations = [
        migrations.CreateModel(
            name="MissedClause",
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
                ("excerpt", models.TextField()),
                ("note", models.TextField(blank=True, default="")),
                ("proposed_rule", models.JSONField(blank=True, default=dict)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("proposed", "Proposed"),
                            ("activated", "Activated"),
                            ("dismissed", "Dismissed"),
                        ],
                        default="proposed",
                        max_length=16,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "contract",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="missed_clauses",
                        to="contracts.contract",
                    ),
                ),
            ],
            options={"ordering": ["-created_at"]},
        ),
    ]
