"""Split a raw WhatsApp .txt export into individual (date, time, sender, message) tuples."""
import re

# Invisible characters WhatsApp exports sometimes insert: left-to-right mark
# (common on iOS, prepended to every line), right-to-left mark, and a
# byte-order mark. Left unstripped, U+200E breaks header matching entirely
# (the line no longer visibly starts with "[" or a digit) and corrupts
# continuation lines that field parsing later depends on.
_INVISIBLE_CHARS = "‎‏﻿"
_INVISIBLE_TABLE = {ord(c): None for c in _INVISIBLE_CHARS}

# Android: "12/09/2026, 08:03 - Member Name: message"
ANDROID_RE = re.compile(
    r'^(\d{1,2}/\d{1,2}/\d{2,4}),\s*(\d{1,2}:\d{2}(?:\s?[APap][Mm])?)\s*-\s*([^:]+):\s?(.*)$'
)
# iOS: "[12/09/2026, 8:03:15 AM] Member Name: message"
IOS_RE = re.compile(
    r'^\[(\d{1,2}/\d{1,2}/\d{2,4}),\s*(\d{1,2}:\d{2}(?::\d{2})?\s?[APap][Mm]?)\]\s*([^:]+):\s?(.*)$'
)


def _strip_invisible(line):
    return line.translate(_INVISIBLE_TABLE)


def _match_header(line):
    m = ANDROID_RE.match(line)
    if m:
        return m.group(1), m.group(2), m.group(3).strip(), m.group(4)
    m = IOS_RE.match(line)
    if m:
        return m.group(1), m.group(2), m.group(3).strip(), m.group(4)
    return None


def split_export(export_text):
    """Yield (date_str, time_str, sender, message_body) for every message in
    a raw WhatsApp .txt export, re-joining multi-line messages onto their
    header. time_str is kept (not just parsed and discarded) since it's
    needed to classify a message as a Commitment (before noon) or an
    Achievement (noon or later)."""
    messages = []
    current = None
    for raw_line in export_text.splitlines():
        line = _strip_invisible(raw_line)
        header = _match_header(line)
        if header:
            if current:
                messages.append(current)
            date_str, time_str, sender, first_line = header
            current = {"date": date_str, "time": time_str, "sender": sender, "lines": [first_line]}
        elif current:
            current["lines"].append(line)
    if current:
        messages.append(current)
    for m in messages:
        yield m["date"], m["time"], m["sender"], "\n".join(m["lines"])
