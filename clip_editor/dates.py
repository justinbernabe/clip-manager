"""Parse a capture timestamp out of a clip's filename.

Game/console capture tools bake the recording time into the filename in a few
shapes; we want that as the post date instead of the import time. Handles:
  - 2026-06-10 11;40;44   (Game Bar / Arc Raiders — semicolon time)
  - Replay_2025-11-08_00-17-04
  - joeyjoejoe99_HaloInfinite_20211124_06-53-40   (compact YYYYMMDD)
  - date-only fallback: 2026-06-10
"""

import os
import re
from datetime import datetime

_PATTERNS = [
    re.compile(r"(\d{4})-(\d{2})-(\d{2})[ _T](\d{2})[;:_.\-](\d{2})[;:_.\-](\d{2})"),
    re.compile(r"(\d{4})(\d{2})(\d{2})[ _T](\d{2})[;:_.\-](\d{2})[;:_.\-](\d{2})"),
]
_DATE_ONLY = re.compile(r"(\d{4})-(\d{2})-(\d{2})")


def parse_capture_date(name):
    """Return a naive datetime parsed from ``name``, or None."""
    base = os.path.basename(name or "")
    for pat in _PATTERNS:
        m = pat.search(base)
        if m:
            try:
                return datetime(*map(int, m.groups()))
            except ValueError:
                pass
    m = _DATE_ONLY.search(base)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            pass
    return None
