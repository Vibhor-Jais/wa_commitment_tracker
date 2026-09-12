"""Parse a single WhatsApp commitment message into field values."""
import re

# Canonical field order (matches the team's fixed template)
FIELDS = [
    "CA noa", "SA noa", "SA Affluent", "Elite", "M0 Value", "CA value",
    "SA value", "RTD", "RD", "LI", "HI", "MF", "SIP",
    "PMJDY", "APY", "PMJJBY", "PMSBY",
]

# Fields that represent a COUNT of accounts/policies rather than a rupee amount
COUNT_FIELDS = {
    "CA noa", "SA noa", "SA Affluent", "Elite", "SIP",
    "PMJDY", "APY", "PMJJBY", "PMSBY",
}

_AMOUNT_RE = re.compile(r'^(\d+(?:\.\d+)?)\s*(lakh|l|k)?$', re.IGNORECASE)


def normalize_amount(raw):
    """Turn '1L', '5 L', '5 lakh', '11k', '25,000', '2' into a plain number.
    Returns None if the field was left blank or couldn't be parsed."""
    if raw is None:
        return None
    s = raw.strip().replace(',', '')
    if s in ('', '-', '--', 'nil', 'na', 'n/a'):
        return None
    s_nospace = re.sub(r'\s+', '', s)
    m = _AMOUNT_RE.match(s_nospace)
    if not m:
        return None
    num = float(m.group(1))
    suffix = (m.group(2) or '').lower()
    if suffix in ('l', 'lakh'):
        num *= 100_000
    elif suffix == 'k':
        num *= 1_000
    return int(num) if num == int(num) else num


def _build_field_patterns():
    patterns = {}
    for field in FIELDS:
        patterns[field] = re.compile(
            r'^\s*' + re.escape(field) + r'\s*[:\-]+\s*(.*)$', re.IGNORECASE
        )
    return patterns


FIELD_PATTERNS = _build_field_patterns()


def parse_message(text):
    """Parse one commitment message body into {field: normalized_value_or_None}.
    Only fields explicitly given a non-blank value are set; everything else
    (not mentioned, or mentioned but left blank) is None - no cross-field
    defaulting between fields."""
    result = {field: None for field in FIELDS}
    unparsed = []  # (field, raw) pairs that had text but didn't normalize cleanly
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        for field, pattern in FIELD_PATTERNS.items():
            m = pattern.match(line)
            if m:
                raw_val = m.group(1).strip()
                val = normalize_amount(raw_val)
                if val is None and raw_val not in ('', '-', '--'):
                    unparsed.append((field, raw_val))
                result[field] = val
                break
    return result, unparsed


def is_commitment_message(text):
    """A message 'counts' if at least one field line has a non-blank value."""
    parsed, _ = parse_message(text)
    return any(v is not None for v in parsed.values())
