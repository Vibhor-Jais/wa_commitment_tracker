"""CLI: python -m wa_commitment_tracker export.txt -o commitment_tracker.xlsx

Incremental by default: if --output already exists, only dates not
already in it get added; existing date sheets are left untouched. Pass
--fresh to ignore any existing file and rebuild from scratch.
"""
import argparse
import os
import sys

from .builder import build_workbook, update_workbook, build_dataframe


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="wa-tracker",
        description="Turn a WhatsApp group's exported chat into a daily commitment tracker (.xlsx).",
    )
    ap.add_argument("export_txt", help="Path to the WhatsApp 'Export chat (without media)' .txt file")
    ap.add_argument(
        "-o", "--output", default="commitment_tracker.xlsx",
        help="Output .xlsx path (default: commitment_tracker.xlsx). If this file already "
             "exists, only new dates are added to it - existing sheets are untouched.",
    )
    ap.add_argument(
        "--fresh", action="store_true",
        help="Ignore any existing file at --output and rebuild it from scratch.",
    )
    args = ap.parse_args(argv)

    with open(args.export_txt, encoding="utf-8") as f:
        export_text = f.read()

    file_exists = os.path.exists(args.output) and not args.fresh

    if file_exists:
        added, skipped, warnings = update_workbook(export_text, args.output, args.output)
        for date_str, sender, unparsed in warnings:
            for field, raw in unparsed:
                print(f"WARNING: couldn't read '{field}' for {sender} on {date_str}: {raw!r}", file=sys.stderr)
        if not added and not skipped:
            print("No commitment messages found in this export. Nothing to write.", file=sys.stderr)
            sys.exit(1)
        print(f"Updated {args.output}")
        if skipped:
            print(f"  already had: {', '.join(skipped)}")
        if added:
            print(f"  added: {', '.join(added)}")
        else:
            print("  nothing new to add - every date in this export was already present")
    else:
        df, warnings = build_dataframe(export_text)
        if df.empty:
            print("No commitment messages found in this export. Nothing to write.", file=sys.stderr)
            sys.exit(1)
        build_workbook(df, args.output)
        for date_str, sender, unparsed in warnings:
            for field, raw in unparsed:
                print(f"WARNING: couldn't read '{field}' for {sender} on {date_str}: {raw!r}", file=sys.stderr)
        dates = list(dict.fromkeys(df["Date"]))
        print(f"Wrote {args.output} (new file)")
        print(f"  added: {', '.join(dates)}")


if __name__ == "__main__":
    main()
