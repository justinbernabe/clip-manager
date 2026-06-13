"""Register existing video files as Media **in place** — no copy, no transcode.

The clips stay exactly where they are on disk; we only create one lightweight
Media row per file pointing at the original. Intended for surfacing a large
existing archive (e.g. the JabLab GameDVR library, ~243 GB) without duplicating
storage or melting the box transcoding.

Requirements:
  * The files must live UNDER MEDIA_ROOT so Django/nginx can serve them. Mount the
    source dir into the container at e.g. media_files/original/gamedvr (read-only)
    — see the JabLab `mediacms` stack.
  * Run with DO_NOT_TRANSCODE_VIDEO=True so media_init() only makes a thumbnail +
    sprite (fast) and serves the original; it never kicks off a full encode.

Usage:
  python manage.py import_library --dir original/gamedvr --limit 20   # try a batch
  python manage.py import_library --dir original/gamedvr               # the rest
"""

import os

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from files.models import Media

from ..dates import parse_capture_date

VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".webm", ".m4v", ".avi", ".flv", ".ts"}


class Command(BaseCommand):
    help = "Register existing videos under MEDIA_ROOT as Media in place (no copy/transcode)."

    def add_arguments(self, parser):
        parser.add_argument("--dir", required=True,
                            help="Directory RELATIVE to MEDIA_ROOT, e.g. 'original/gamedvr'")
        parser.add_argument("--user", default=None,
                            help="Owner username (default: first superuser)")
        parser.add_argument("--limit", type=int, default=0,
                            help="Stop after N new registrations (0 = all)")
        parser.add_argument("--dry-run", action="store_true",
                            help="List what would be registered, change nothing")

    def handle(self, *args, **opts):
        from users.models import User

        if not settings.DO_NOT_TRANSCODE_VIDEO:
            self.stderr.write(self.style.WARNING(
                "DO_NOT_TRANSCODE_VIDEO is False — registered clips would be queued for "
                "full transcode. Set it True before importing a large library."))

        rel = opts["dir"].strip("/")
        root = os.path.join(settings.MEDIA_ROOT, rel)
        if not os.path.isdir(root):
            self.stderr.write(self.style.ERROR(
                f"Not a directory under MEDIA_ROOT: {root}\n"
                f"(MEDIA_ROOT={settings.MEDIA_ROOT}) — is the source mounted there?"))
            return

        if opts["user"]:
            owner = User.objects.filter(username=opts["user"]).first()
        else:
            owner = User.objects.filter(is_superuser=True).order_by("id").first()
        if not owner:
            self.stderr.write(self.style.ERROR("No owner user found."))
            return

        registered = skipped = 0
        for dirpath, _dirs, files in os.walk(root):
            for fn in sorted(files):
                if os.path.splitext(fn)[1].lower() not in VIDEO_EXTS:
                    continue
                abs_path = os.path.join(dirpath, fn)
                # Name stored on the FileField, relative to MEDIA_ROOT — points
                # straight at the existing file, no copy.
                name = os.path.relpath(abs_path, settings.MEDIA_ROOT)

                if Media.objects.filter(media_file=name).exists():
                    skipped += 1
                    continue

                if opts["dry_run"]:
                    self.stdout.write(f"would register: {name}")
                    registered += 1
                else:
                    media = Media(user=owner, title=os.path.splitext(fn)[0])
                    media.media_file.name = name  # no .save() on the field => no copy
                    media.save()  # post_save -> media_init -> thumbnail+sprite, serves original
                    # Post date = capture time from the filename, not import time.
                    dt = parse_capture_date(fn)
                    if dt:
                        aware = timezone.make_aware(dt) if timezone.is_naive(dt) else dt
                        Media.objects.filter(pk=media.pk).update(add_date=aware, edit_date=aware)
                    registered += 1
                    self.stdout.write(f"[{registered}] {name} -> {media.friendly_token}")

                if opts["limit"] and registered >= opts["limit"]:
                    self._summary(registered, skipped, opts["dry_run"])
                    return

        self._summary(registered, skipped, opts["dry_run"])

    def _summary(self, registered, skipped, dry):
        verb = "would register" if dry else "registered"
        self.stdout.write(self.style.SUCCESS(
            f"{verb} {registered}, skipped {skipped} (already present)."))
