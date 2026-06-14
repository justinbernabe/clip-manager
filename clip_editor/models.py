from django.conf import settings
from django.db import models


class AutomationRun(models.Model):
    """A record of a JoeyDVR automation run (whole-library job), for the Tools page."""

    name = models.CharField(max_length=64, db_index=True)
    status = models.CharField(
        max_length=20,
        choices=(("running", "Running"), ("done", "Done"), ("failed", "Failed")),
        default="running",
    )
    result = models.TextField(blank=True, default="")
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-started_at"]

    def __str__(self):
        return f"{self.name} ({self.status})"


class EditProject(models.Model):
    """A non-destructive edit. Holds an EDL (see EDITOR.md) against one or more
    source Media; rendering emits a brand-new Media and never touches the source.
    """

    STATUS = (
        ("draft", "Draft"),
        ("rendering", "Rendering"),
        ("done", "Done"),
        ("failed", "Failed"),
    )

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="edit_projects",
    )
    title = models.CharField(max_length=200, default="Untitled edit")
    status = models.CharField(max_length=20, choices=STATUS, default="draft", db_index=True)

    # The timeline. EDL schema v1 lives in EDITOR.md. JSON so the UI owns the
    # shape and the backend stays format-agnostic across roadmap phases.
    edl = models.JSONField(default=dict, blank=True)

    # Set when a render completes. FK to the produced clip.
    output_media = models.ForeignKey(
        "files.Media",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="produced_by_edits",
    )
    error = models.TextField(blank=True, default="")

    add_date = models.DateTimeField(auto_now_add=True)
    edit_date = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-add_date"]

    def __str__(self):
        return f"{self.title} ({self.status})"
