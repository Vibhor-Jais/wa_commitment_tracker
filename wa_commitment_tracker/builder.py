"""Turn parsed commitment/achievement messages into a DataFrame, and the
DataFrame into a formatted Excel workbook - either a fresh one
(build_workbook) or an incremental update onto an existing workbook that
only adds sheets for dates it doesn't already have (update_workbook).

Layout per date sheet: one row per member. Each template field gets TWO
columns side by side - Commitment and Achievement - under a merged header
with the field name. A live 'Present (Commitment)' / 'Present
(Achievement)' column per row flags whether that member filled in
anything of that type, and a Total row at the bottom sums everything.
"""
import pandas as pd
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter

from .parser import FIELDS, COUNT_FIELDS, parse_message, is_commitment_message
from .splitter import split_export
from .classifier import classify_message_type, COMMITMENT, ACHIEVEMENT

HEADER_FONT = Font(name="Arial", bold=True, color="FFFFFF")
HEADER_FILL = PatternFill("solid", fgColor="4472C4")
SUBHEADER_FONT = Font(name="Arial", bold=True, color="FFFFFF")
SUBHEADER_FILL = PatternFill("solid", fgColor="8FAADC")
LABEL_FONT = Font(name="Arial", bold=True)
VALUE_FONT = Font(name="Arial")
TOTAL_FONT = Font(name="Arial", bold=True)
TOTAL_FILL = PatternFill("solid", fgColor="D9E1F2")
THIN = Side(style="thin", color="000000")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)

UNKNOWN = "Unknown"
NON_DATE_SHEETS = {"Daily Summary", "Notes"}

NOTES_LINES = [
    "Layout: one sheet per day, one row per member. Each field has TWO",
    "columns side by side - Commitment and Achievement - under a merged",
    "header with the field name. Type is 'Commitment' if the message was",
    "sent before 12:00 noon, 'Achievement' if sent at noon or later",
    "('Unknown' columns only appear if some timestamp couldn't be read -",
    "check the warnings printed when the tool ran).",
    "",
    "'Present (Commitment)' / 'Present (Achievement)' per row is a live",
    "formula (1 if that member filled in anything of that type that day,",
    "else 0). The Total row sums every column, including the Present",
    "columns (so it also shows the day's present-member count per type).",
    "'Daily Summary' pulls those same Total-row numbers per date - all of",
    "this recalculates if you edit the sheet.",
    "",
    "This workbook is updated INCREMENTALLY: re-running the tool against a",
    "growing export only adds sheets for dates not already present here -",
    "existing date sheets are never re-parsed or overwritten.",
    "",
    "Parsing rules applied:",
    "- A field is filled in only if the member explicitly stated a value for it;",
    "  unmentioned or blank fields are left empty (no cross-field defaulting).",
    "- 'noa', SIP, PMJDY, APY, PMJJBY, PMSBY, SA Affluent and Elite are treated as",
    "  ACCOUNT/POLICY COUNTS (e.g. '1' = one account).",
    "- M0 Value, CA value, SA value, RTD, RD, LI, HI, MF are treated as RUPEE AMOUNTS.",
    "  '1L' / '1 lakh' -> 100000, '11k' -> 11000, '25,000' -> 25000.",
    "- A message counts as a commitment/achievement only if at least one field",
    "  was filled in (a bare 'Good morning' with nothing filled in doesn't count).",
    "- If a member posts MORE THAN ONCE in the same noon-defined window (e.g. two",
    "  messages both before noon), only the LAST one is used - it is not merged",
    "  field-by-field with the earlier message. Confirm this is the behavior you",
    "  want before relying on it for real data with frequent corrections.",
]


def build_dataframe(export_text):
    """Parse a raw WhatsApp export into a tidy DataFrame: one row per
    (Date, Member, Type) message, one column per template field.
    Messages with nothing filled in (e.g. a bare 'Good morning') are
    skipped, since they don't count as a commitment/achievement and don't
    mark the member present. Type is Commitment if sent before 12:00
    (noon), Achievement if sent at 12:00 or later; 'Unknown' if the
    timestamp couldn't be parsed (flagged as a warning, not dropped)."""
    rows = []
    warnings = []
    for date_str, time_str, sender, body in split_export(export_text):
        if not is_commitment_message(body):
            continue
        parsed, unparsed = parse_message(body)
        if unparsed:
            warnings.append((date_str, sender, unparsed))
        msg_type = classify_message_type(time_str)
        if msg_type is None:
            warnings.append((date_str, sender, [("(time)", time_str)]))
            msg_type = UNKNOWN
        row = {"Date": date_str, "Member": sender, "Type": msg_type}
        row.update(parsed)
        rows.append(row)
    df = pd.DataFrame(rows, columns=["Date", "Member", "Type"] + FIELDS)
    return df, warnings


def normalize_date_key(date_str):
    """The key used both as a sheet name and to detect 'is this date
    already in the workbook' - so a date is only ever represented one
    way, regardless of which run added it."""
    return date_str.strip().replace("/", "-")[:31]


def _border_range(ws, min_row, max_row, min_col, max_col):
    for r in range(min_row, max_row + 1):
        for c in range(min_col, max_col + 1):
            ws.cell(row=r, column=c).border = BORDER


def _pivot_day(subset, types):
    """member (first-seen order) -> type -> {field: value}. If a member
    posted more than one message of the same type on the same day, the
    LAST one wins (whole-row replace) - see README limitations."""
    members = list(dict.fromkeys(subset["Member"]))
    data = {}
    for member in members:
        data[member] = {}
        for t in types:
            match = subset[(subset["Member"] == member) & (subset["Type"] == t)]
            if len(match):
                last = match.iloc[-1]
                data[member][t] = {f: last[f] for f in FIELDS}
            else:
                data[member][t] = {f: None for f in FIELDS}
    return members, data


def _column_layout(types):
    field_start_col = 2
    field_col_map = {}
    col = field_start_col
    for field in FIELDS:
        field_col_map[field] = {}
        for t in types:
            field_col_map[field][t] = col
            col += 1
    presence_col_map = {}
    for t in types:
        presence_col_map[t] = col
        col += 1
    last_col = col - 1
    return field_col_map, presence_col_map, last_col


def _write_date_sheet(wb, ws_summary, summary_row_i, date, subset, types,
                       field_col_map, presence_col_map, last_col):
    """Write one date's sheet and its corresponding Daily Summary row.
    Shared by build_workbook (fresh) and update_workbook (incremental)."""
    members, data = _pivot_day(subset, types)
    sheet_name = normalize_date_key(date)
    ws = wb.create_sheet(sheet_name)

    n_members = len(members)
    data_start = 3
    total_row = data_start + n_members

    ws.merge_cells(start_row=1, end_row=2, start_column=1, end_column=1)
    mcell = ws.cell(row=1, column=1, value="Member")
    mcell.font = HEADER_FONT
    mcell.fill = HEADER_FILL
    ws.cell(row=2, column=1).fill = HEADER_FILL

    for field in FIELDS:
        c0 = field_col_map[field][types[0]]
        c1 = field_col_map[field][types[-1]]
        ws.merge_cells(start_row=1, end_row=1, start_column=c0, end_column=c1)
        fcell = ws.cell(row=1, column=c0, value=field)
        fcell.font = HEADER_FONT
        fcell.fill = HEADER_FILL
        fcell.alignment = Alignment(horizontal="center")
        for t in types:
            scell = ws.cell(row=2, column=field_col_map[field][t], value=t)
            scell.font = SUBHEADER_FONT
            scell.fill = SUBHEADER_FILL
            scell.alignment = Alignment(horizontal="center")

    for t in types:
        pc = presence_col_map[t]
        ws.merge_cells(start_row=1, end_row=2, start_column=pc, end_column=pc)
        pcell = ws.cell(row=1, column=pc, value=f"Present ({t})")
        pcell.font = HEADER_FONT
        pcell.fill = HEADER_FILL
        pcell.alignment = Alignment(horizontal="center", wrap_text=True)

    for i, member in enumerate(members, start=data_start):
        lcell = ws.cell(row=i, column=1, value=member)
        lcell.font = LABEL_FONT
        for field in FIELDS:
            for t in types:
                val = data[member][t][field]
                if val is None or (isinstance(val, float) and pd.isna(val)):
                    continue
                ccol = field_col_map[field][t]
                cell = ws.cell(row=i, column=ccol, value=val)
                cell.font = VALUE_FONT
                cell.number_format = "0" if field in COUNT_FIELDS else "#,##0"
        for t in types:
            cell_refs = [f"{get_column_letter(field_col_map[f][t])}{i}" for f in FIELDS]
            formula = f"=IF(COUNTA({','.join(cell_refs)})>0,1,0)"
            pcell = ws.cell(row=i, column=presence_col_map[t], value=formula)
            pcell.font = VALUE_FONT
            pcell.alignment = Alignment(horizontal="center")

    tlabel = ws.cell(row=total_row, column=1, value="Total")
    tlabel.font = TOTAL_FONT
    tlabel.fill = TOTAL_FILL
    last_data_row = total_row - 1
    for field in FIELDS:
        for t in types:
            ccol = field_col_map[field][t]
            col_letter = get_column_letter(ccol)
            formula = f"=SUM({col_letter}{data_start}:{col_letter}{last_data_row})"
            tcell = ws.cell(row=total_row, column=ccol, value=formula)
            tcell.font = TOTAL_FONT
            tcell.fill = TOTAL_FILL
            tcell.number_format = "0" if field in COUNT_FIELDS else "#,##0"
    for t in types:
        ccol = presence_col_map[t]
        col_letter = get_column_letter(ccol)
        formula = f"=SUM({col_letter}{data_start}:{col_letter}{last_data_row})"
        tcell = ws.cell(row=total_row, column=ccol, value=formula)
        tcell.font = TOTAL_FONT
        tcell.fill = TOTAL_FILL
        tcell.number_format = "0"

    ws.column_dimensions["A"].width = 16
    for c in range(2, last_col + 1):
        ws.column_dimensions[get_column_letter(c)].width = 13
    ws.freeze_panes = "B3"
    _border_range(ws, 1, total_row, 1, last_col)

    ws_summary.cell(row=summary_row_i, column=1, value=date).font = VALUE_FONT
    for k, t in enumerate(types, start=2):
        col_letter = get_column_letter(presence_col_map[t])
        formula = f"='{sheet_name}'!{col_letter}{total_row}"
        fcell = ws_summary.cell(row=summary_row_i, column=k, value=formula)
        fcell.font = VALUE_FONT
        fcell.number_format = "0"


def _new_summary_workbook(types):
    wb = Workbook()
    ws_summary = wb.active
    ws_summary.title = "Daily Summary"
    summary_headers = ["Date"] + [f"Present ({t})" for t in types]
    for col, header in enumerate(summary_headers, start=1):
        cell = ws_summary.cell(row=1, column=col, value=header)
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.alignment = Alignment(horizontal="center")
    ws_summary.column_dimensions["A"].width = 14
    for col in range(2, 2 + len(types)):
        ws_summary.column_dimensions[get_column_letter(col)].width = 20
    return wb, ws_summary


def _write_notes_sheet(wb):
    ws3 = wb.create_sheet("Notes")
    for i, line in enumerate(NOTES_LINES, start=1):
        ws3.cell(row=i, column=1, value=line).font = Font(name="Arial", italic=True)
    ws3.column_dimensions["A"].width = 90


def build_workbook(df, output_path):
    """Write the Date/Member/Type/field DataFrame out as a BRAND NEW
    formatted .xlsx (use this the first time; use update_workbook to add
    to an existing file)."""
    types = [COMMITMENT, ACHIEVEMENT]
    if not df.empty and (df["Type"] == UNKNOWN).any():
        types.append(UNKNOWN)

    wb, ws_summary = _new_summary_workbook(types)
    dates = list(dict.fromkeys(df["Date"])) if not df.empty else []
    field_col_map, presence_col_map, last_col = _column_layout(types)

    for row_i, date in enumerate(dates, start=2):
        subset = df[df["Date"] == date]
        _write_date_sheet(wb, ws_summary, row_i, date, subset, types,
                           field_col_map, presence_col_map, last_col)

    _border_range(ws_summary, 1, max(len(dates) + 1, 1), 1, 1 + len(types))
    _write_notes_sheet(wb)
    wb.save(output_path)


def update_workbook(export_text, existing_workbook, output_path):
    """Incrementally update a commitment tracker: parse export_text (a
    cumulative WhatsApp export, however far back it goes), and add a
    sheet ONLY for dates not already present in existing_workbook -
    existing date sheets are left completely untouched.

    existing_workbook: a path, file-like object, or bytes of a workbook
    previously produced by this tool, or None to build fresh.

    Returns (added_dates, skipped_dates, warnings) - skipped_dates are
    dates found in the export that were already in existing_workbook.
    """
    df, warnings = build_dataframe(export_text)
    if df.empty:
        return [], [], warnings

    all_dates = list(dict.fromkeys(df["Date"]))

    if existing_workbook is not None:
        wb = load_workbook(existing_workbook)
        if "Daily Summary" not in wb.sheetnames:
            raise ValueError(
                "existing_workbook has no 'Daily Summary' sheet - "
                "is this really a file produced by this tool?"
            )
        ws_summary = wb["Daily Summary"]
        existing_keys = {name for name in wb.sheetnames if name not in NON_DATE_SHEETS}
        next_row = ws_summary.max_row + 1
        # types already used in this workbook's Daily Summary header
        existing_types = [
            ws_summary.cell(row=1, column=c).value.replace("Present (", "").rstrip(")")
            for c in range(2, ws_summary.max_column + 1)
        ]
    else:
        wb = None
        existing_keys = set()
        existing_types = []
        next_row = 2

    new_dates = [d for d in all_dates if normalize_date_key(d) not in existing_keys]
    skipped_dates = [d for d in all_dates if normalize_date_key(d) in existing_keys]

    if not new_dates:
        if wb is not None:
            wb.save(output_path)  # write out unchanged, so output_path always exists after a call
        return [], skipped_dates, warnings

    new_types = [COMMITMENT, ACHIEVEMENT]
    if (df["Type"] == UNKNOWN).any():
        new_types.append(UNKNOWN)
    # keep column layout consistent with whatever this workbook already uses,
    # only widening it (e.g. adding Unknown) if this batch actually needs it
    types = existing_types if set(existing_types) >= set(new_types) and existing_types else new_types

    if wb is None:
        wb, ws_summary = _new_summary_workbook(types)

    field_col_map, presence_col_map, last_col = _column_layout(types)

    for date in new_dates:
        subset = df[df["Date"] == date]
        _write_date_sheet(wb, ws_summary, next_row, date, subset, types,
                           field_col_map, presence_col_map, last_col)
        next_row += 1

    _border_range(ws_summary, 1, next_row - 1, 1, 1 + len(types))

    if "Notes" not in wb.sheetnames:
        _write_notes_sheet(wb)

    wb.save(output_path)
    return new_dates, skipped_dates, warnings
