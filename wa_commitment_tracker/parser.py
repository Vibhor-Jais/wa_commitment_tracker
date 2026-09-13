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

_AMOUNT_RE = re.compile(r'^(\d+(?:\.\d+)?)\s*(lakhs?|lacs?|l|k)?', re.IGNORECASE)

# Values that mean "genuinely blank", not "couldn't be parsed" - WhatsApp
# appends this tag to any edited message, and it can land on a field line
# that the person actually left empty. Treated as blank, not a warning.
_BLANK_VALUES = {'', '-', '--', 'nil', 'na', 'n/a', '<this message was edited>'}


def _is_blank(raw):
    return raw is not None and raw.strip().lower() in _BLANK_VALUES


def normalize_amount(raw):
    """Turn '1L', '5 L', '5 lakh', '5 lac', '5 lacs', '11k', '25,000', '2'
    into a plain number. Returns None if the field was left blank or
    couldn't be parsed.

    Deliberately a PREFIX match, not a full-string match: real messages
    carry all kinds of trailing noise after the actual number - a
    redundant unit word ('1 noa'), WhatsApp's own '<This message was
    edited>' tag, shorthand like '1/0'. Whatever number+unit appears at
    the start is taken as the value and everything after it is ignored,
    rather than rejecting the whole field as unparseable. If a field
    genuinely uses 'N/M' notation to mean something other than 'N is the
    value, ignore the rest', this will read it as just N - check that
    assumption against a few real messages if your team uses that
    convention on purpose."""
    if raw is None or _is_blank(raw):
        return None
    s = raw.strip().replace(',', '')
    s_nospace = re.sub(r'\s+', '', s)
    m = _AMOUNT_RE.match(s_nospace)
    if not m:
        return None
    num = float(m.group(1))
    suffix = (m.group(2) or '').lower()
    if suffix in ('l', 'lakh', 'lakhs', 'lac', 'lacs'):
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
                if val is None and not _is_blank(raw_val):
                    unparsed.append((field, raw_val))
                result[field] = val
                break
    return result, unparsed


def is_commitment_message(text):
    """A message 'counts' if at least one field line has a non-blank value."""
    parsed, _ = parse_message(text)
    return any(v is not None for v in parsed.values())
