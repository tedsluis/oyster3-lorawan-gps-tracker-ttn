import io
import re
from contextlib import redirect_stdout

import pytest

from tests.conftest import REPO, load_script

README = (REPO / "README.md").read_text()


def dry_run(port):
    module = load_script("configure-using-downlinks.py", f"configure_readme_{port}")
    out = io.StringIO()
    with redirect_stdout(out):
        assert module.main(["--downlink", str(port), "--config", str(REPO / "config.yaml")]) == 0
    return out.getvalue().rstrip("\n")


def readme_blocks():
    pattern = r"\$ python \./configure-using-downlinks\.py --downlink (\d+)\n(.*?)\n````"
    return [(int(port), block) for port, block in re.findall(pattern, README, re.S)]


def test_readme_shows_every_downlink():
    ports = sorted({port for port, _ in readme_blocks()})
    assert ports == [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 30, 31, 32, 33, 34, 35]


@pytest.mark.parametrize("port, block", readme_blocks())
def test_readme_example_output_is_the_real_dry_run(port, block):
    # Audit F27: the examples showed payloads of the old, wrong encoder
    assert block == dry_run(port)


def test_readme_has_no_stale_or_misspelled_content():
    for stale in (
        "Byte Array: 02",
        "Bitstring",
        "./files/",
        "requiered",
        "Requierments",
        "completly",
        "Streeetmap",
        "comfirmed",
        "formating",
        "pip install bitstring",
        "APLICATION",
        "7 days",
    ):
        assert stale not in README, stale


def test_readme_relative_links_exist():
    for target in re.findall(r"\]\((\./[^)#]+|[\w-]+\.(?:md|png|yaml|example))\)", README):
        assert (REPO / target).exists(), target


def test_readme_explains_acknowledgements_and_storage_delay():
    # Audit A4 and F22
    assert "**only once**, on its next uplink attempt" in README
    assert "not meant for real-time use" in README


def test_readme_documents_privacy_and_cdns():
    # Audit F29
    section = README.split("## Privacy", 1)[1]
    for text in ("0700", "0600", "cdn.jsdelivr.net", "OpenStreetMap", "DELETE FROM uplinks"):
        assert text in section


def test_readme_links_official_docs_and_only_the_allowed_local_pdfs():
    # Audit F28, revised: three Digital Matter PDFs are kept locally on purpose; the
    # Integration spec is only linked at its official location.
    assert "validated against the *Oyster 3 LoRaWAN Integration* spec, revision 1.3" in README
    allowed = {
        "Oyster3-LoRaWAN-Configuration-and-Usage-Guide-Digital-Matter.pdf",
        "Oyster3-LoRaWAN-Datasheet-Digital-Matter-2024.pdf",
        "Oyster3-LoRaWAN-GPS-Battery-Powered-LoRa-Tracker.pdf",
    }
    assert {path.name for path in (REPO / "docs").glob("*.pdf")} == allowed
    for name in allowed:
        assert f"(./docs/{name})" in README
