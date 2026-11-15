# Voortgang auditfixes
Branch: fix/audit-2026-11 · Basiscommit: 358adea · Laatst bijgewerkt: 2026-11-15 17:50 CET

## Huidige stand
Fase: 1 · Bezig met: - · Tests: 0 groen

## Items
| ID | Fase | Status | Test(s) | Notitie |
|----|------|--------|---------|---------|
| 0.1 baseline | 0 | KLAAR | - | Werkboom van de audit is door Ted gecommit als 358adea ("fix"); diffstat identiek aan de audit, incl. read-json.py en uplinks.py. Geen extra baseline-commit nodig. |
| 0.2 voortgangsbestand | 0 | KLAAR | - | |
| 0.3 tooling | 0 | KLAAR | - | venv buiten de repo (/tmp), requirements-dev.txt, pyproject.toml (ruff+pytest), tests/, .gitignore aangevuld. pytest: 0 tests (exit 5), ruff: groen. |
| 0.4 audit + spec gelezen | 0 | KLAAR | - | Auditrapport en spec §3 volledig gelezen; golden waarden onafhankelijk nagerekend vóór de start. |
| F06 | 1 | KLAAR | tests/test_webserver_settings.py | Default 127.0.0.1 + debug uit; APP_HOST/APP_PORT/APP_DEBUG. README: firewall-advies vervangen door WSGI+reverse proxy-uitleg. |
| LOCK zendslot | 1 | KLAAR | tests/test_send_lock.py | configure-using-downlinks.py --send stopt direct (exit≠0, melding 'audit F01'). Gaat er pas af in fase 3 na groene golden tests. |
| F10 | 1 | TODO | | |
| F05 | 2 | TODO | | |
| F20 | 2 | TODO | | |
| F31 | 2 | TODO | | |
| F08 (decoder) | 2 | TODO | | |
| F04 | 3 | TODO | | |
| A2 | 3 | TODO | | |
| F26 | 3 | TODO | | |
| F01 | 3 | TODO | | |
| F02 | 3 | TODO | | |
| F07 | 3 | TODO | | |
| F16 | 3 | TODO | | |
| F25 | 3 | TODO | | |
| A3 | 3 | TODO | | |
| A6 | 3 | TODO | | |
| UNLOCK zendslot eraf | 3 | TODO | | |
| F17 | 4 | TODO | | |
| F14 | 4 | TODO | | |
| F21 | 4 | TODO | | |
| F12 | 4 | TODO | | |
| F22 | 4 | TODO | | |
| F11 | 4 | TODO | | Codedeel; key roteren/splitsen doet Ted. |
| F09 | 5 | TODO | | |
| F13 | 5 | TODO | | |
| F08 | 6 | TODO | | |
| F15 | 6 | TODO | | |
| F19 | 6 | TODO | | |
| F23 | 6 | TODO | | |
| F24 | 6 | TODO | | |
| F30 | 6 | TODO | | |
| F27 | 7 | TODO | | |
| F28 | 7 | TODO | | |
| A1 | 7 | OVERGESLAGEN | - | Claim klopt niet: README linkt naar 4 PDF's en alle 4 staan in docs/. Afgedekt door F28 (D2). |
| F18 | 7 | TODO | | |
| F29 | 7 | TODO | | |
| F03 | 7 | TODO | | Runbook; uitvoeren doet Ted. |
| A4 | 7 | TODO | | |
| A5 | 7 | TODO | | |
| 8 eindcontrole | 8 | TODO | | |

Statussen: TODO · BEZIG · KLAAR · OVERGESLAGEN (met reden) · WACHT-OP-TED

## Beslissingen
D1 MIT (Ted Sluis) · D2 PDF's uit de werkboom, officiële links · D3 SQLite `data/uplinks.sqlite3` · D4 `Europe/Amsterdam` via `APP_TIMEZONE` · D5 Python ≥ 3.10 · D6 niet pushen · D7 push-integratie buiten scope · D8 CDN's alleen documenteren.

Correcties op de opdracht (door Ted akkoord bevonden vóór de start):
1. A1 klopt niet (zie tabel).
2. A4: de bron is spec §3.4 (inleiding "Oyster 1 Compatible Downlinks"), niet §2.
3. A2 deels al gedaan: de drie signed velden van DL4 waren al `signed-integer`.
4. Fase 0.1: read-json.py en uplinks.py zaten al in 358adea.
5. Fase 6: `templates/map_content.html` blijft in `.gitignore` (oud gegenereerd bestand; mag door het contentbeleid niet geopend of verwijderd worden).
6. `audit-report.md` en `CLAUDE-CODE-FIX-PROMPT.md` staan lokaal uitgesloten via `.git/info/exclude` en worden nooit gecommit.
7. Port 4-specvoorbeeld heeft fixFailed=true: de test controleert de coördinaten onder `cached`.
8. Python 3.10: eigen timestampparser (geen `Z`/nanoseconden in `fromisoformat`); lokaal alleen 3.15 beschikbaar, 3.10 wordt in CI getest.

## Afwijkingen t.o.v. audit

## Open vragen voor Ted

## Vervolg (buiten scope)

## Logboek
- 2026-11-15 17:50 CET start, fase 0 (0.1 bleek al gedaan door commit 358adea)
- 2026-11-15 17:55 CET Fase 0 afgerond
