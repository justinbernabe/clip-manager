"""Async render: walk a project's EDL, render with ffmpeg, and create a NEW Media
from the result. Saving the Media triggers MediaCMS's normal post_save ->
media_init -> encode pipeline, so the produced clip transcodes + thumbnails like
any upload.
"""

import os

from celery import shared_task
from django.core.files import File

from files.helpers import produce_friendly_token
from files.models import Media

from .models import EditProject
from .render import RenderError, render_edl


def _resolve_source_path(friendly_token):
    """EDL clip 'source' (a friendly_token) -> absolute path of its media file."""
    media = Media.objects.filter(friendly_token=friendly_token).first()
    if not media or not media.media_file:
        return None
    return media.media_file.path


@shared_task(name="clip_editor.render_edit_project")
def render_edit_project(project_id):
    project = EditProject.objects.filter(id=project_id).first()
    if not project:
        return

    project.status = "rendering"
    project.error = ""
    project.save(update_fields=["status", "error", "edit_date"])

    # Render to a temp path under MEDIA_ROOT, then hand the file to a new Media.
    token = produce_friendly_token()
    work_name = f"clip_edit_{project.id}_{token}.mp4"
    work_path = os.path.join(settings_media_tmp(), work_name)

    try:
        render_edl(project.edl, _resolve_source_path, work_path)

        media = Media(
            user=project.owner,
            title=project.title or "Edited clip",
            description=f"Rendered by clip-manager editor from project #{project.id}.",
        )
        with open(work_path, "rb") as fh:
            # FileField.save(commit=True) persists the Media -> post_save fires ->
            # media_init() runs -> encode() kicks off. One call does it all.
            media.media_file.save(work_name, File(fh), save=True)

        project.output_media = media
        project.status = "done"
        project.save(update_fields=["output_media", "status", "edit_date"])
    except RenderError as exc:
        project.status = "failed"
        project.error = str(exc)
        project.save(update_fields=["status", "error", "edit_date"])
    except Exception as exc:  # noqa: BLE001 - surface anything else to the UI
        project.status = "failed"
        project.error = f"unexpected: {exc}"
        project.save(update_fields=["status", "error", "edit_date"])
    finally:
        if os.path.exists(work_path):
            try:
                os.remove(work_path)
            except OSError:
                pass


def settings_media_tmp():
    """A writable scratch dir inside the media volume for the in-flight render."""
    from django.conf import settings

    tmp = os.path.join(settings.MEDIA_ROOT, "editor_tmp")
    os.makedirs(tmp, exist_ok=True)
    return tmp
