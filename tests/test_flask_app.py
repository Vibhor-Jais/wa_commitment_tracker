import base64
import io
import re
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "api"))
from api.index import app  # noqa: E402

SAMPLE_EXPORT = """10/09/2026, 08:00 - Alice: Good morning,
CA noa:-
SA noa:- 1
SA Affluent -
Elite:-
M0 Value:-
Ca value:-
Sa value:- 2L
RTD:-
RD:-
LI:-
HI:-
MF:-
SIP:-
PMJDY:-
APY:-
PMJJBY:-
PMSBY:-
"""


def test_index_page_loads():
    client = app.test_client()
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"Generate / Update tracker" in resp.data


def test_generate_with_no_file_shows_error():
    client = app.test_client()
    resp = client.post("/generate", data={}, content_type="multipart/form-data")
    assert resp.status_code == 400
    assert b"Please choose" in resp.data


def test_generate_produces_valid_downloadable_workbook():
    client = app.test_client()
    resp = client.post(
        "/generate",
        data={"export_txt": (io.BytesIO(SAMPLE_EXPORT.encode()), "chat.txt")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")
    assert "Added: 10/09/2026" in html

    m = re.search(r'href="data:[^;]+;base64,([^"]+)"', html)
    assert m is not None
    xlsx_bytes = base64.b64decode(m.group(1))
    assert xlsx_bytes[:2] == b"PK"  # xlsx is a zip archive
