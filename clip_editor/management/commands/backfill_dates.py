"""Backfill Media post dates from the capture time in each clip's filename.

In-place imported clips all land with add_date = import time ("6 hours ago").
This rewrites add_date/edit_date to the real recording time parsed from the
filename, so the library sorts and reads by when the clip was actually captured.

    python manage.py backfill_dates            # all media with a parseable name
    python manage.py backfill_dates --dry-run
"""

import os

from django.core.management.base import BaseCommand
from django.utils import timezone

from files.models import Media

from ..dates import parse_capture_date


class Command(BaseCommand):
    help = "Set Media add_date/edit_date from the capture time in the filename."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **opts):
        updated = skipped = 0
        qs = Media.objects.exclude(media_file="").exclude(media_file__isnull=True)
        for media in qs.iterator():
            dt = parse_capture_date(os.path.basename(media.media_file.name or ""))
            if not dt:
                skipped += 1
                continue
            aware = timezone.make_aware(dt) if timezone.is_naive(dt) else dt
            if opts["dry_run"]:
                self.stdout.write(f"{media.friendly_token}: {media.add_date} -> {aware}")
            else:
                Media.objects.filter(pk=media.pk).update(add_date=aware, edit_date=aware)
            updated += 1
        verb = "would update" if opts["dry_run"] else "updated"
        self.stdout.write(self.style.SUCCESS(
            f"{verb} {updated}, skipped {skipped} (no parseable date)."))
