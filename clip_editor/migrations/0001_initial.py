from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("files", "__first__"),
    ]

    operations = [
        migrations.CreateModel(
            name="EditProject",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(default="Untitled edit", max_length=200)),
                ("status", models.CharField(choices=[("draft", "Draft"), ("rendering", "Rendering"), ("done", "Done"), ("failed", "Failed")], db_index=True, default="draft", max_length=20)),
                ("edl", models.JSONField(blank=True, default=dict)),
                ("error", models.TextField(blank=True, default="")),
                ("add_date", models.DateTimeField(auto_now_add=True)),
                ("edit_date", models.DateTimeField(auto_now=True)),
                ("output_media", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="produced_by_edits", to="files.media")),
                ("owner", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="edit_projects", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-add_date"]},
        ),
    ]
