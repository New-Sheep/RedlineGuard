# Generated manually for LLM context agents

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("review", "0008_magical_llm_sprint"),
    ]

    operations = [
        migrations.AddField(
            model_name="reviewrun",
            name="agent_assist",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
