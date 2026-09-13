# trigger redeploy
"""Personal-use UI for wa-commitment-tracker.

Run locally:   streamlit run app.py
Deploy free:   push this repo to GitHub, then create an app at
               https://share.streamlit.io pointing at app.py

Stateless by design: nothing is stored on the server between visits.
Each time, you upload (1) your cumulative WhatsApp export and (2) the
tracker workbook you downloaded last time (skip this the very first
time). The app figures out which dates in the export aren't in that
workbook yet, adds only those, and gives you a new file to download -
which becomes input (2) again tomorrow.
"""
import io

import streamlit as st

from wa_commitment_tracker.builder import update_workbook

st.set_page_config(page_title="WA Commitment Tracker", page_icon="📊", layout="centered")

st.title("📊 WhatsApp Commitment Tracker")
st.caption(
    "Upload your team's WhatsApp export and get back an Excel tracker, "
    "updated only for the days it doesn't already have."
)

with st.expander("How to export your WhatsApp chat"):
    st.markdown(
        "In WhatsApp: open the group → **More** → **Export chat** → "
        "**Without Media**. Send the resulting `.txt` file to yourself "
        "and upload it below. You can export the *whole* chat history "
        "each time - only genuinely new dates get added."
    )

st.subheader("1. Upload your files")
export_file = st.file_uploader("WhatsApp export (.txt)", type=["txt"])
existing_file = st.file_uploader(
    "Your tracker from last time (.xlsx) - skip this on the very first run",
    type=["xlsx"],
)

if st.button("Generate / Update tracker", type="primary", disabled=export_file is None):
    export_text = export_file.read().decode("utf-8", errors="replace")
    existing_bytes = io.BytesIO(existing_file.read()) if existing_file is not None else None

    output_buf = io.BytesIO()
    try:
        added, skipped, warnings = update_workbook(export_text, existing_bytes, output_buf)
    except ValueError as e:
        st.error(
            f"That doesn't look like a tracker this tool made ({e}). "
            "Leave the second upload empty to start a fresh tracker."
        )
        st.stop()

    st.subheader("2. Result")

    if not added and not skipped:
        st.warning(
            "No commitment/achievement messages found in this export - "
            "nothing to write. Check the file is a real 'Export chat (without media)' export."
        )
        st.stop()

    if skipped:
        st.info(f"Already had: {', '.join(skipped)}")

    if added:
        st.success(f"Added: {', '.join(added)}")
    else:
        st.info("Nothing new - every date in this export was already in your uploaded tracker.")

    if warnings:
        with st.expander(f"⚠️ {len(warnings)} field(s) couldn't be read - click to see details"):
            for date_str, sender, unparsed in warnings:
                for field, raw in unparsed:
                    st.text(f"{date_str} · {sender}: couldn't read '{field}' = {raw!r}")

    output_buf.seek(0)
    st.download_button(
        "⬇️ Download updated tracker",
        data=output_buf,
        file_name="commitment_tracker.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary",
    )
    st.caption("Save this file - upload it as \"Your tracker from last time\" on your next run.")
