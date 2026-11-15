# Voortgang auditfixes
Branch: fix/audit-2026-11 · Basiscommit: 358adea · Laatst bijgewerkt: 2026-11-15 17:50 CET

## Huidige stand
Fase: 3 · Bezig met: - · Tests: 104 groen

## Items
| ID | Fase | Status | Test(s) | Notitie |
|----|------|--------|---------|---------|
| 0.1 baseline | 0 | KLAAR | - | Werkboom van de audit is door Ted gecommit als 358adea ("fix"); diffstat identiek aan de audit, incl. read-json.py en uplinks.py. Geen extra baseline-commit nodig. |
| 0.2 voortgangsbestand | 0 | KLAAR | - | |
| 0.3 tooling | 0 | KLAAR | - | venv buiten de repo (/tmp), requirements-dev.txt, pyproject.toml (ruff+pytest), tests/, .gitignore aangevuld. pytest: 0 tests (exit 5), ruff: groen. |
| 0.4 audit + spec gelezen | 0 | KLAAR | - | Auditrapport en spec §3 volledig gelezen; golden waarden onafhankelijk nagerekend vóór de start. |
| F06 | 1 | KLAAR | tests/test_webserver_settings.py | Default 127.0.0.1 + debug uit; APP_HOST/APP_PORT/APP_DEBUG. README: firewall-advies vervangen door WSGI+reverse proxy-uitleg. |
| LOCK zendslot | 1 | KLAAR | tests/test_send_lock.py | configure-using-downlinks.py --send stopt direct (exit≠0, melding 'audit F01'). Gaat er pas af in fase 3 na groene golden tests. |
| F10 | 1 | KLAAR | tests/test_requirements.py | requirements.txt (gepind op geteste versies) + requirements-dev.txt; README: pip install -r requirements.txt. bitstring<5 tijdelijk tot F07. |
| F05 | 2 | KLAAR | tests/test_uplinks.py, tests/test_webserver_decoding.py | Koers = (byte8>>2)*5.625 in oyster3/uplinks.py en webserver.py. Eigenschapstest 64 waarden. Lokaal: 3.985 port-1-records, 0 met koers ≥ 360. |
| F20 | 2 | KLAAR | tests/test_uplinks.py::test_port3_spec_example, ::test_port31_spec_example | uplinks.py gebruikt decode_uplink voor port 3 en 31 (port 31 was niet gedecodeerd). Volledige CLI-herbouw in fase 4. |
| F31 | 2 | KLAAR | tests/test_webserver_decoding.py | Batterij in volt (LSb 25 mV), comment gecorrigeerd. |
| F08 (decoder) | 2 | KLAAR | tests/test_uplinks.py::test_only_gnss_uplinks_are_positions | decode_uplink geeft per poort een type; POSITION_PORTS = {1,4,33}. Plotten volgt in fase 6. |
| F04 | 3 | KLAAR | tests/test_config_layout.py | Validator (naam-offset = byte/bit/length, geen overlap, geen gaten, lengte = spec) + 8 correcties in config.yaml (DL4 ×3, DL6, DL10 byte 6 gesplitst (waarde 1), DL30, DL34, DL35). Validator vond vóór de fix 19 problemen, alle binnen de auditbevindingen. |
| A2 | 3 | KLAAR | tests/test_config_layout.py::test_validator_detects_inconsistent_types, ::test_signed_reserved_and_joineui_fields_are_typed | DL6 6.0-6.4 en DL9 byte 5 → signed-integer (DL4 was al goed); 5 meerbits reserved-velden boolean → integer; min/max waar de spec een bereik noemt; endian: big bij DL8 JoinEUI. Validator controleert types. |
| F26 | 3 | KLAAR | tests/test_config_defaults.py | Echte defaults: DL5 byte 6 = 28 (10 km/h), DL10 bytes 4/5 = 0 (Auto), DL32 byte 1 = 6 (94 mG). default: bij alle 135 velden (behalve sequence). Kopcomment herschreven. CLI-waarschuwing bij afwijkende waarden: zie commit van F01 (test_cli_warns_about_non_default_values). |
| F01 | 3 | KLAAR | tests/test_downlink_encoder.py (golden 18, sequence, round-trip ×90, CLI dry-run 18) | Nieuwe encoder via BitWriter (LSb-first). CLI herschreven bovenop oyster3/downlinks.py; zendslot blijft tot UNLOCK. |
| F02 | 3 | KLAAR | tests/test_downlink_encoder.py::test_dl30_multi_byte_fields_are_little_endian, ::test_dl7_channel_mask_is_little_endian, ::test_dl8_join_eui_stays_big_endian | Meerbytevelden little-endian; alleen endian: big (DL8 JoinEUI) big-endian. |
| F07 | 3 | KLAAR | tests/test_requirements.py | bitstring verwijderd uit code en requirements.txt. De oude voorbeelduitvoer in de README (kolomkop 'Bitstring') wordt in fase 7 (F27) opnieuw gegenereerd. |
| F16 | 3 | KLAAR | tests/test_downlink_validation.py | parse_value strikt (boolean alleen true/false/0/1; B/H-suffix alleen bij integer-types); waarde moet passen (nooit afkappen); signed via two's complement na bereikcontrole; min/max afgedwongen; foutmelding noemt het veld; CLI geeft exit 2 i.p.v. een payload. |
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
- Tijdelijk: ruff sluit de nog niet herschreven legacy-scripts uit (webserver.py, ack.py, uplinks.py, read-json.py) en negeert E501 in de legacy send-code van configure-using-downlinks.py. Wordt opgeheven zodra die bestanden in fase 4-6 herschreven zijn.

## Open vragen voor Ted

## Vervolg (buiten scope)

## Logboek
- 2026-11-15 17:50 CET start, fase 0 (0.1 bleek al gedaan door commit 358adea)
- 2026-11-15 17:55 CET Fase 0 afgerond
- 2026-11-15 18:05 CET Fase 1 afgerond
- 2026-11-15 18:25 CET Fase 2 afgerond
