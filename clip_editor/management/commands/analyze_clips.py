"""Analyze existing clips and tag them with `no-audio` / `hdr`.

    python manage.py analyze_clips            # all video Media
    python manage.py analyze_clips --limit 50

Reads each clip's media info (ffprobe colour transfer for HDR; ffprobe + a short
volumedetect for silent/missing audio) and applies the matching tags. Cheap to
re-run — it just re-adds the same tags. The scheduled `process_new_clips` task
applies these automatically to new clips going forward.
"""

import os

from django.core.management.base import BaseCommand

from files.models import Media

from ...ingest import analyze_tags


class Command(BaseCommand):
    help = "Tag clips with no-audio / hdr from their media info."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=0)

    def handle(self, *args, **opts):
        from files.models import Tag
        from users.models import User

        owner = User.objects.filter(is_superuser=True).order_by("id").first()
        scanned = tagged = 0
        qs = (Media.objects.filter(media_type="video")
              .exclude(media_file="").exclude(media_file__isnull=True))
        for media in qs.iterator():
            try:
                path = media.media_file.path
            except Exception:
                continue
            if not os.path.exists(path):
                continue
            scanned += 1
            tags = analyze_tags(path)
            for tname in tags:
                tag, _ = Tag.objects.get_or_create(title=tname, defaults={"user": owner})
                media.tags.add(tag)
            if tags:
                tagged += 1
                self.stdout.write(f"{media.friendly_token}: {', '.join(tags)}")
            if opts["limit"] and scanned >= opts["limit"]:
                break
        self.stdout.write(self.style.SUCCESS(f"scanned {scanned}, tagged {tagged}"))
