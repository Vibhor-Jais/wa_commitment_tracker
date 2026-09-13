"""Flask version of wa-commitment-tracker's UI, for hosts like Vercel that
don't support Streamlit's WebSocket requirement. Plain HTTP form submit +
file download - no persistent connection needed at all, unlike Streamlit.
"""
import io
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from flask import Flask, request, send_file, Response
from wa_commitment_tracker.builder import update_workbook

app = Flask(__name__)

PAGE = """<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>WhatsApp Commitment Tracker</title>
<style>
  body { font-family: -apple-system, Arial, sans-serif; max-width: 640px;
         margin: 40px auto; padding: 0 16px; color: #222; }
  h1 { font-size: 1.5rem; }
  .field { margin: 20px 0; }
  label { display: block; font-weight: 600; margin-bottom: 6px; }
  .hint { color: #666; font-size: 0.9rem; margin-top: 4px; }
  button { background: #ff4b4b; color: white; border: none; padding: 12px 24px;
           font-size: 1rem; border-radius: 6px; cursor: pointer; }
  button:hover { background: #e03e3e; }
  .msg { padding: 12px 16px; border-radius: 6px; margin: 16px 0; }
  .msg.success { background: #d4edda; color: #155724; }
  .msg.info { background: #d1ecf1; color: #0c5460; }
  .msg.warn { background: #fff3cd; color: #856404; }
  .msg.error { background: #f8d7da; color: #721c24; }
  a.download { display: inline-block; margin-top: 12px; background: #ff4b4b;
               color: white; padding: 10px 20px; border-radius: 6px; text-decoration: none; }
</style>
</head>
<body>
<h1>📊 WhatsApp Commitment Tracker</h1>
<p>Upload your team's WhatsApp export and get back an Excel tracker, updated
only for the days it doesn't already have.</p>

%%RESULT%%

<form method="POST" action="/generate" enctype="multipart/form-data">
  <div class="field">
    <label>WhatsApp export (.txt)</label>
    <input type="file" name="export_txt" accept=".txt" required>
  </div>
  <div class="field">
    <label>Your tracker from last time (.xlsx) — skip on the very first run</label>
    <input type="file" name="existing_xlsx" accept=".xlsx">
  </div>
  <button type="submit">Generate / Update tracker</button>
</form>
</body>
</html>
"""


def render(result=""):
    return PAGE.replace("%%RESULT%%", result)


@app.route("/", methods=["GET"])
def index():
    return render()


@app.route("/generate", methods=["POST"])
def generate():
    export_file = request.files.get("export_txt")
    if not export_file or export_file.filename == "":
        return render(
            '<div class="msg error">Please choose a WhatsApp export .txt file.</div>'
        ), 400

    export_text = export_file.read().decode("utf-8", errors="replace")

    existing_file = request.files.get("existing_xlsx")
    existing_bytes = None
    if existing_file and existing_file.filename:
        existing_bytes = io.BytesIO(existing_file.read())

    output_buf = io.BytesIO()
    try:
        added, skipped, warnings = update_workbook(export_text, existing_bytes, output_buf)
    except ValueError as e:
        return render(
            f'<div class="msg error">That doesn\'t look like a tracker this '
            f'tool made ({e}). Leave the second upload empty to start fresh.</div>'
        ), 400

    if not added and not skipped:
        return render(
            '<div class="msg warn">No commitment/achievement messages found '
            'in this export - nothing to write.</div>'
        )

    msgs = []
    if skipped:
        msgs.append(f'<div class="msg info">Already had: {", ".join(skipped)}</div>')
    if added:
        msgs.append(f'<div class="msg success">Added: {", ".join(added)}</div>')
    else:
        msgs.append('<div class="msg info">Nothing new - every date was already present.</div>')
    if warnings:
        msgs.append(f'<div class="msg warn">{len(warnings)} field(s) could not be read - '
                     f'check with the CLI/Notes sheet for details.</div>')

    output_buf.seek(0)
    import base64
    b64 = base64.b64encode(output_buf.getvalue()).decode("ascii")
    href = (
        "data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;"
        f"base64,{b64}"
    )
    msgs.append(
        f'<a class="download" href="{href}" download="commitment_tracker.xlsx">'
        f'⬇️ Download updated tracker</a>'
    )

    return render("".join(msgs))


# Vercel's Python runtime looks for a WSGI-callable named `app`
