from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("clip_editor", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="AutomationRun",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(db_index=True, max_length=64)),
                ("status", models.CharField(choices=[("running", "Running"), ("done", "Done"), ("failed", "Failed")], default="running", max_length=20)),
                ("result", models.TextField(blank=True, default="")),
                ("started_at", models.DateTimeField(auto_now_add=True)),
                ("finished_at", models.DateTimeField(blank=True, null=True)),
            ],
            options={"ordering": ["-started_at"]},
        ),
    ]
