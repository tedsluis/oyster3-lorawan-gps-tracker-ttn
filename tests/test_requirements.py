import re

from tests.conftest import REPO


def requirement_names():
    names = []
    for line in (REPO / "requirements.txt").read_text().splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            names.append(re.split(r"[<>=!~ ]", line, maxsplit=1)[0].lower())
    return names


def test_runtime_requirements_are_complete_and_real():
    names = requirement_names()
    for needed in ("flask", "folium", "requests", "pyyaml"):
        assert needed in names
    assert "request" not in names  # does not exist on PyPI (audit F10)


def test_every_requirement_is_pinned():
    for line in (REPO / "requirements.txt").read_text().splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            assert re.search(r"(==|<)", line), line


def test_readme_installs_from_requirements_file():
    readme = (REPO / "README.md").read_text()
    assert "pip install -r requirements.txt" in readme
    assert not re.search(r"pip install [^\n]*\brequest\b(?!s)", readme)
