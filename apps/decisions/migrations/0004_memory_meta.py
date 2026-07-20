from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("decisions", "0003_sprint5_memory_ux"),
    ]

    operations = [
        migrations.AddField(
            model_name="decision",
            name="memory_meta",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
