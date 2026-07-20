# Hash chain + audit kind expansions

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("decisions", "0005_wishlist_undo_audit"),
    ]

    operations = [
        migrations.AddField(
            model_name="auditevent",
            name="prev_hash",
            field=models.CharField(blank=True, default="", max_length=64),
        ),
        migrations.AddField(
            model_name="auditevent",
            name="entry_hash",
            field=models.CharField(blank=True, default="", max_length=64),
        ),
        migrations.AlterField(
            model_name="auditevent",
            name="kind",
            field=models.CharField(
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
                    ("llm_call", "LLM call"),
                    ("missed_clause", "Missed clause propose"),
                ],
                max_length=32,
            ),
        ),
    ]
