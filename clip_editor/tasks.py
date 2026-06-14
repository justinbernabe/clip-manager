"""Async render: walk a project's EDL, render with ffmpeg, and create a NEW Media
from the result. Saving the Media triggers MediaCMS's normal post_save ->
media_init -> encode pipeline, so the produced clip transcodes + thumbnails like
any upload.
"""

import os

from celery import shared_task
from django.conf import settings
from django.core.files import File
from django.utils import timezone

from files.helpers import produce_friendly_token
from files.models import Media

from .dates import parse_capture_date
from .ingest import VIDEO_EXTS, analyze_tags, detect_game, retag_to_hvc1
from .models import EditProject
from .render import RenderError, render_edl


@shared_task(name="process_new_clips", queue="long_tasks", soft_time_limit=60 * 60 * 2)
def process_new_clips():
    """Beat task: ingest clips newly dropped into the library folder.

    For each NEW video under MEDIA_ROOT/gamedvr (not yet a Media): retag hev1->hvc1
    in place (lossless) so phones play it, then register it in place with the
    capture-date as the post date and a best-effort game category. Already-known
    files are skipped, so this is cheap to run on a schedule.
    """
    from files.models import Category, Tag
    from users.models import User

    base = os.path.join(settings.MEDIA_ROOT, "gamedvr")
    if not os.path.isdir(base):
        return {"skipped": "no gamedvr dir"}

    owner = User.objects.filter(is_superuser=True).order_by("id").first()
    if not owner:
        return {"skipped": "no owner"}

    retagged = registered = 0
    for dirpath, _dirs, files in os.walk(base):
        for fn in sorted(files):
            if os.path.splitext(fn)[1].lower() not in VIDEO_EXTS:
                continue
            abs_path = os.path.join(dirpath, fn)
            name = os.path.relpath(abs_path, settings.MEDIA_ROOT)
            if Media.objects.filter(media_file=name).exists():
                continue  # already ingested — skip (keeps this cheap)

            if retag_to_hvc1(abs_path):
                retagged += 1

            media = Media(user=owner, title=os.path.splitext(fn)[0])
            media.media_file.name = name
            media.save()
            dt = parse_capture_date(fn)
            if dt:
                aware = timezone.make_aware(dt) if timezone.is_naive(dt) else dt
                Media.objects.filter(pk=media.pk).update(add_date=aware, edit_date=aware)
            game = detect_game(name)
            if game:
                cat, _ = Category.objects.get_or_create(title=game, defaults={"user": owner})
                media.category.add(cat)
            for tname in analyze_tags(abs_path):
                tag, _ = Tag.objects.get_or_create(title=tname, defaults={"user": owner})
                media.tags.add(tag)
            registered += 1

    return {"retagged": retagged, "registered": registered}


# Registry of whole-library automations surfaced on the JoeyDVR Tools admin page.
# key == management command name; (label, description, runs_on_new_too)
AUTOMATIONS = [
    ("backfill_dates", "Capture dates", "Set each clip's post date from its filename.", True),
    ("categorize_games", "Game categories", "Sort clips into per-game categories from the filename.", True),
    ("retag_hevc", "HEVC → hvc1 retag", "Make HEVC clips playable on Safari/iOS (lossless, in place).", True),
    ("analyze_clips", "Audio / HDR tags", "Tag clips 'noaudio' and 'hdr' from their media info.", True),
]
AUTOMATION_NAMES = {a[0] for a in AUTOMATIONS}


@shared_task(name="run_automation", queue="long_tasks", soft_time_limit=60 * 60 * 3)
def run_automation(name):
    """Run a whole-library automation (a management command) and record the result."""
    from io import StringIO

    from django.core.management import call_command

    from .models import AutomationRun

    if name not in AUTOMATION_NAMES:
        return "unknown"
    run = AutomationRun.objects.create(name=name, status="running")
    out = StringIO()
    try:
        call_command(name, stdout=out, stderr=out)
        run.status, run.result = "done", out.getvalue()[-3000:]
    except Exception as exc:  # noqa: BLE001 - surface failures on the Tools page
        run.status, run.result = "failed", (out.getvalue() + "\n" + str(exc))[-3000:]
    run.finished_at = timezone.now()
    run.save(update_fields=["status", "result", "finished_at"])
    return run.status


def _resolve_source_path(friendly_token):
    """EDL clip 'source' (a friendly_token) -> absolute path of its media file."""


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
