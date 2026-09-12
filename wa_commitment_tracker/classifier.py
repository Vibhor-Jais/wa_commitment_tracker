"""Classify a message by when it was sent: before noon = Commitment
(what a member is planning to do that day), noon or later = Achievement
(what they actually did)."""
from datetime import datetime

COMMITMENT = "Commitment"
ACHIEVEMENT = "Achievement"

# Try 12-hour-with-AM/PM formats first (they're more specific), then 24-hour.
_TIME_FORMATS = [
    "%I:%M:%S %p", "%I:%M %p", "%I:%M:%S%p", "%I:%M%p",
    "%H:%M:%S", "%H:%M",
]


def parse_hour(time_str):
    """Return the 24-hour hour (0-23) a WhatsApp timestamp string
    represents, or None if it can't be parsed."""
    s = time_str.strip().upper().replace("AM", " AM").replace("PM", " PM")
    s = " ".join(s.split())  # collapse repeated/odd spacing
    for fmt in _TIME_FORMATS:
        try:
            return datetime.strptime(s, fmt).hour
        except ValueError:
            continue
    return None


def classify_message_type(time_str):
    """Commitment if sent before 12:00 (noon), Achievement if sent at
    12:00 or later. Returns None if the time couldn't be parsed, so the
    caller can flag it instead of silently mis-classifying."""
    hour = parse_hour(time_str)
    if hour is None:
        return None
    return COMMITMENT if hour < 12 else ACHIEVEMENT
