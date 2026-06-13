"""Pure ffmpeg renderer: an EDL -> one output file.

Phase 1: a single video track of [in, out] segments cut from one or more source
clips and concatenated in order. We reuse MediaCMS's proven recipe from
``files.helpers.trim_video_method`` — stream-copy segment cut (``-ss/-t -c copy``)
plus the concat demuxer — which is fast and lossless, but requires segments to
share codec/params. Mixed sources fall through to ``RenderError`` for now; the
P2 re-encode path (``filter_complex concat``) plugs in at ``_concat``.

This module is deliberately framework-light (no Django model imports) so it's
unit-testable and so the Celery task in tasks.py owns all the DB/Media work.
"""

import os
import shutil
import tempfile

from django.conf import settings

from files.helpers import run_command


class RenderError(Exception):
    pass


def _ffmpeg():
    return settings.FFMPEG_COMMAND


def cut_segment(src_path, start, end, out_path):
    """Cut [start, end] out of src_path into out_path (stream copy)."""
    duration = float(end) - float(start)
    if duration <= 0:
        raise RenderError(f"non-positive segment duration: {start}..{end}")
    cmd = [
        _ffmpeg(), "-y",
        "-ss", str(start),
        "-i", src_path,
        "-t", str(duration),
        "-c", "copy",
        "-avoid_negative_ts", "1",
        out_path,
    ]
    run_command(cmd)
    if not (os.path.exists(out_path) and os.path.getsize(out_path) > 0):
        raise RenderError(f"ffmpeg produced no output for segment {start}..{end}")


def _concat(segment_paths, out_path, work_dir):
    """Concat segments via the concat demuxer (stream copy)."""
    concat_list = os.path.join(work_dir, "concat_list.txt")
    with open(concat_list, "w") as f:
        for seg in segment_paths:
            # ffmpeg concat demuxer wants single-quoted, escaped paths
            f.write("file '%s'\n" % seg.replace("'", "'\\''"))
    cmd = [
        _ffmpeg(), "-y",
        "-f", "concat", "-safe", "0",
        "-i", concat_list,
        "-c", "copy",
        out_path,
    ]
    run_command(cmd)
    if not (os.path.exists(out_path) and os.path.getsize(out_path) > 0):
        raise RenderError("concat produced no output (mixed codecs? P2 re-encode path needed)")


def render_edl(edl, resolve_source_path, dest_path):
    """Render ``edl`` to ``dest_path``.

    ``resolve_source_path(friendly_token) -> absolute path`` is injected by the
    caller (tasks.py) so this stays decoupled from the Media model.
    Returns ``dest_path`` on success, raises ``RenderError`` otherwise.
    """
    tracks = (edl or {}).get("tracks") or []
    video_tracks = [t for t in tracks if t.get("kind", "video") == "video"]
    if not video_tracks:
        raise RenderError("EDL has no video track")
    if len(video_tracks) > 1:
        raise RenderError("multi-track compositing is a P3+ feature")
    clips = video_tracks[0].get("clips") or []
    if not clips:
        raise RenderError("video track has no clips")

    if any(c.get("transition_in") or c.get("transition_out") for c in clips):
        raise RenderError("transitions are a P4 feature")

    _, ext = os.path.splitext(dest_path)
    ext = ext or ".mp4"

    with tempfile.TemporaryDirectory(dir=settings.TEMP_DIRECTORY) as work:
        segments = []
        for i, clip in enumerate(clips):
            src = resolve_source_path(clip["source"])
            if not src or not os.path.exists(src):
                raise RenderError(f"source not found: {clip.get('source')}")
            seg = os.path.join(work, f"seg_{i}{ext}")
            cut_segment(src, clip["in"], clip["out"], seg)
            segments.append(seg)

        out_tmp = os.path.join(work, f"out{ext}")
        if len(segments) == 1:
            shutil.copy2(segments[0], out_tmp)
        else:
            _concat(segments, out_tmp, work)

        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        shutil.copy2(out_tmp, dest_path)

    return dest_path
