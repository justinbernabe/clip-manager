"""Losslessly retag HEVC `hev1` clips to `hvc1` in place so phones/Safari play them.

    python manage.py retag_hevc                 # under MEDIA_ROOT/gamedvr
    python manage.py retag_hevc --dir gamedvr

No re-encode (`-c copy`), no quality loss — just the container tag + faststart.
The scheduled `process_new_clips` task does this automatically for new files; this
command is for a one-off sweep of existing clips.
"""

import os

from django.conf import settings
from django.core.management.base import BaseCommand

from ...ingest import VIDEO_EXTS, retag_to_hvc1


class Command(BaseCommand):
    help = "Retag HEVC hev1 clips to hvc1 in place (lossless)."

    def add_arguments(self, parser):
        parser.add_argument("--dir", default="gamedvr", help="Directory relative to MEDIA_ROOT")

    def handle(self, *args, **opts):
        root = os.path.join(settings.MEDIA_ROOT, opts["dir"].strip("/"))
        if not os.path.isdir(root):
            self.stderr.write(self.style.ERROR(f"Not a directory: {root}"))
            return
        retagged = scanned = 0
        for dirpath, _dirs, files in os.walk(root):
            for fn in sorted(files):
                if os.path.splitext(fn)[1].lower() not in VIDEO_EXTS:
                    continue
                scanned += 1
                if retag_to_hvc1(os.path.join(dirpath, fn)):
                    retagged += 1
                    self.stdout.write(f"retagged: {fn}")
        self.stdout.write(self.style.SUCCESS(f"retagged {retagged} / scanned {scanned}"))
