# wa-commitment-tracker

Turns a bank sales team's daily WhatsApp messages into a daily Excel
tracker against the team's fixed template (CA noa, SA noa, SA Affluent,
Elite, M0 Value, CA value, SA value, RTD, RD, LI, HI, MF, SIP, PMJDY, APY,
PMJJBY, PMSBY) — with each field split into a **Commitment** column
(posted before noon) and an **Achievement** column (posted at noon or
later). **Incremental**: re-run it against a growing export and it only
adds sheets for dates it doesn't already have.

Ships as a small Streamlit UI (`app.py`) and a CLI (`wa-tracker`), both
backed by the same `wa_commitment_tracker` package.

## Giving this to someone else to run themselves

Two ways, depending on how technical the recipient is.

### Docker (works even if they have no Python installed)

They need only [Docker](https://www.docker.com/products/docker-desktop/)
installed. From this folder:

```bash
docker compose up --build
```

Then open `http://localhost:8501`. That's it — no `pip install`, no
Python version to worry about. To stop it, `Ctrl+C` then
`docker compose down`.

To hand someone a runnable image directly instead of the source folder,
build and export it as a single file:

```bash
docker build -t wa-commitment-tracker .
docker save wa-commitment-tracker -o wa-commitment-tracker.tar
```

They load and run it with:

```bash
docker load -i wa-commitment-tracker.tar
docker run -p 8501:8501 wa-commitment-tracker
```

If you also have a Docker Hub account, `docker push` it there instead
and they just `docker run -p 8501:8501 <your-dockerhub-username>/wa-commitment-tracker`
— no file transfer needed at all.

### From source (for anyone comfortable with Python)

```bash
pip install -r requirements.txt
streamlit run app.py          # UI, opens at localhost:8501
# or
pip install -e .
wa-tracker export.txt -o commitment_tracker.xlsx   # CLI
```

### A shared hosted link instead

If you'd rather run *one* copy yourself and just share the URL (so
nobody needs Docker or Python at all), see the "Deploy to Streamlit
Community Cloud" steps in this project's chat history / your own
Anthropic conversation — push this repo to GitHub and deploy it at
[share.streamlit.io](https://share.streamlit.io). Worth knowing: the app
is stateless (see below), so this works fine for multiple people using
the same link, each with their own files — but their WhatsApp data does
pass through Streamlit's servers in that case, which running it
themselves (Docker or from source) avoids entirely.

## How the UI works

1. Upload your WhatsApp export (`.txt`) — export the *whole* chat
   history every time; the app figures out what's new.
2. Upload the tracker `.xlsx` you downloaded last time (skip this the
   very first run).
3. Click **Generate / Update**, then download the result.
4. Next time: repeat with a fresher export and the file you just
   downloaded.

The app is **stateless** — it stores nothing between visits or between
users. State lives entirely in the workbook you keep downloading and
re-uploading. This is deliberate: it's what makes Docker/local/hosted
all behave identically, and it means the tool never accumulates a copy
of your team's sales data anywhere you're not directly holding it.

## Parsing rules

- A field is only filled in if the member explicitly gave it a value.
  Anything they left blank or didn't mention stays blank — no field ever
  gets another field's value.
- `CA noa`, `SA noa`, `SA Affluent`, `Elite`, `SIP`, `PMJDY`, `APY`,
  `PMJJBY`, `PMSBY` are treated as **counts** (accounts/policies opened).
- `M0 Value`, `CA value`, `SA value`, `RTD`, `RD`, `LI`, `HI`, `MF` are
  treated as **rupee amounts**. `1L` / `1 lakh` → 100000, `11k` → 11000,
  `25,000` → 25000.
- A message counts as a commitment/achievement only if at least one field
  is filled in — a bare "Good morning" with everything blank doesn't count.
- **Commitment vs Achievement** is decided purely by the message
  timestamp: before 12:00 noon → Commitment column, at or after 12:00
  noon → Achievement column. Unparseable timestamps get an `Unknown`
  pair of columns (only added if this ever actually happens) and a
  printed warning — never silently dropped or guessed into one bucket.
- **Incremental updates**: a date already present as a sheet in the
  workbook you upload/point at is never re-parsed or overwritten. To
  force a re-parse of a specific date, delete that date's sheet (and its
  row in Daily Summary) from the workbook before uploading it back in.

## Output layout

- One sheet per day, one row per member. Every field has two columns
  side by side under a merged header — Commitment and Achievement.
  `Present (Commitment)` / `Present (Achievement)` columns (live
  formulas) flag whether that member filled in anything of that type.
  A **Total** row sums every column, including the Present columns.
- **Daily Summary** sheet: pulls each day's Total-row present counts.
- **Notes** sheet: the parsing rules, in plain English.

## Project layout

```
app.py                        Streamlit UI
Dockerfile, docker-compose.yml, .dockerignore
LICENSE                       MIT - swap this out if you want different terms
wa_commitment_tracker/
  parser.py      field-level parsing + amount normalization (k/L/lakh)
  splitter.py    splits a raw WhatsApp .txt export into (date, time, sender, message)
  classifier.py  Commitment/Achievement classification from message time
  builder.py     DataFrame -> formatted .xlsx, fresh (build_workbook) or
                 incremental (update_workbook)
  cli.py         command-line entry point
tests/
  test_parser.py
  test_classifier.py
  test_builder.py
  test_incremental.py
```

## Known limitations / next steps

- Field labels are matched against the exact template spelling
  (case-insensitive, tolerant of `:`, `-`, or `:-` separators, and
  surrounding spaces). A member who renames a field or adds a typo the
  patterns don't cover shows up as a warning, and that field is left
  blank rather than guessed.
- If a member posts **more than once in the same noon-defined window**
  on the same day, only the last one is used — a whole-row replace, not
  a field-by-field merge with the earlier message.
- Dates are matched as strings (`/` normalized to `-`), not parsed into
  real calendar dates. Fine as long as one WhatsApp export always
  formats dates the same way (true for a single phone/group).
- No authentication of any kind - anyone with the URL (if hosted) or the
  running container's port can use it. Fine for personal/internal use
  behind a private link or on localhost; add your own auth layer (e.g. a
  reverse proxy with basic auth) before exposing it more broadly.
