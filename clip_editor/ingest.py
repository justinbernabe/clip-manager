"""Ongoing ingest helpers for new clips dropped into the library folder.

Two jobs, both in place / no duplication:
  - retag_to_hvc1: HEVC tagged `hev1` -> `hvc1` (+faststart), lossless `-c copy`
    remux so phones/Safari will play it. Same video/audio bytes, new container.
  - detect_game: best-effort game category from the filename/path.

Used by the `process_new_clips` Celery beat task (clip_editor/tasks.py) and the
`retag_hevc` management command.
"""

import os
import shutil
import subprocess
import tempfile

from django.conf import settings

VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".webm", ".m4v"}
FFMPEG = getattr(settings, "FFMPEG_COMMAND", "ffmpeg")
FFPROBE = getattr(settings, "FFPROBE_COMMAND", "ffprobe")

GAME_KEYWORDS = [
    ("arc raiders", "Arc Raiders"),
    ("haloinfinite", "Halo Infinite"), ("halo infinite", "Halo Infinite"), ("halo", "Halo Infinite"),
    ("battlefield", "Battlefield"), ("bf6", "Battlefield"), ("bf2042", "Battlefield"),
    ("fortnite", "Fortnite"),
    ("satisfactory", "Satisfactory"),
    ("forza", "Forza Horizon"),
    ("rocket league", "Rocket League"), ("rocketleague", "Rocket League"),
]


def probe_codec_tag(path):
    """Return (codec_name, codec_tag_string) lowercased for the first video stream."""
    try:
        out = subprocess.run(
            [FFPROBE, "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=codec_name,codec_tag_string", "-of", "csv=p=0", path],
            capture_output=True, text=True, timeout=60,
        ).stdout.strip()
        parts = out.split(",")
        return (parts[0].lower() if parts else "", parts[1].lower() if len(parts) > 1 else "")
    except Exception:
        return ("", "")


def retag_to_hvc1(path):
    """If `path` is HEVC tagged hev1, losslessly retag to hvc1 + faststart, in place.
    Returns True if it retagged, False otherwise."""
    codec, tag = probe_codec_tag(path)
    if not (codec == "hevc" and tag == "hev1"):
        return False
    fd, tmp = tempfile.mkstemp(suffix=".mp4", dir=os.path.dirname(path))
    os.close(fd)
    try:
        subprocess.run(
            [FFMPEG, "-y", "-loglevel", "error", "-i", path, "-map", "0",
             "-c", "copy", "-tag:v", "hvc1", "-movflags", "+faststart", tmp],
            check=True, timeout=3600,
        )
        if os.path.getsize(tmp) > 0:
            shutil.move(tmp, path)
            return True
    except Exception:
        pass
    if os.path.exists(tmp):
        try:
            os.remove(tmp)
        except OSError:
            pass
    return False


def detect_game(path):
    low = path.lower()
    for kw, cat in GAME_KEYWORDS:
        if kw in low:
            return cat
    return None
