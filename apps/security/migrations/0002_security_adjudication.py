# Generated manually for LLM context agents

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("security", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="securityevent",
            name="adjudication",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
