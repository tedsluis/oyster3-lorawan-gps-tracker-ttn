# Voortgang auditfixes
Branch: fix/audit-2026-11 · Basiscommit: 358adea · Laatst bijgewerkt: 2026-11-15 17:50 CET

## Huidige stand
Fase: 5 · Bezig met: - · Tests: 346 groen

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
| F25 | 3 | KLAAR | tests/test_cli_arguments.py | --downlink alleen 1-12 en 30-35 (configure, ack.py, uplinks.py); sequence 0-127 inclusief. Overbodige ack-argumenten van uplinks.py verdwijnen in fase 4. |
| A3 | 3 | KLAAR | tests/test_send_path.py | f_port gaat als int (args.downlink) naar send_downlink; voorheen de string uit de YAML-sleutel. Gemockt, niets verstuurd. |
| A6 | 3 | KLAAR | tests/test_cli_arguments.py::test_configure_sequence_override_is_used_in_payload, tests/test_downlink_encoder.py::test_sequence_override | --sequencenumber overschrijft de waarde uit config.yaml. |
| UNLOCK zendslot eraf | 3 | KLAAR | tests/test_send_path.py::test_send_never_happens_with_an_invalid_value | Slot verwijderd nadat alle golden tests groen waren. tests/test_send_lock.py vervangen door een veiligheidstest: --send verstuurt nooit bij een ongeldige waarde. |
| F17 | 4 | KLAAR | tests/test_ttn.py::test_urls_are_built_from_console_and_region, ::test_no_hardcoded_tenant_host_outside_the_client | Downlink- en storage-URL uit TTN_CONSOLE + TTN_REGION in oyster3/ttn.py; User-Agent meegestuurd. Geen host meer in scripts. |
| F14 | 4 | KLAAR | tests/test_ttn.py (401, timeout, connection error, 403, lege respons), tests/test_send_path.py, tests/test_ack_cli.py::test_api_error_gives_clean_exit | timeout=30, raise_for_status → TTNError zonder API-key in de melding; geen hergebruik van oude response; CLI's geven exitcode 1 met melding. Webserver valt bij een TTN-fout terug op lokale data. |
| F21 | 4 | KLAAR | tests/test_ttn.py::test_parse_storage_response* (7 varianten + API-fout + ongeldige JSON) | parse_storage_response: regel voor regel, lege regels overslaan, met/zonder event-stream. |
| F12 | 4 | KLAAR | tests/test_ttn.py::test_wait_for_ack_*, ::test_find_ack_matches_sequence_and_port, tests/test_ack_cli.py | Aware UTC (eigen parser, ook nanoseconden), match op sequence én poort, stopt na MATCH (ook ack.py), --attempts/--interval instelbaar, ack.py --history. Sequence in de wachtlus komt uit de verzonden payload. |
| F22 | 4 | KLAAR | tests/test_ttn.py::test_wait_for_ack_stops_after_match_and_only_asks_for_new_uplinks | Pollen met after=<verzendtijd − 1 min> en limit=100. README-tekst volgt in fase 7 (F27/A4). |
| F11 | 4 | KLAAR | tests/test_ttn.py::test_reading_and_sending_use_separate_keys, ::test_example_environment_file_has_placeholders_only, ::test_downlink_key_falls_back_to_api_key | Codedeel: optionele TTN_DOWNLINK_API_KEY (terugval TTN_API_KEY), export-env-vars.sh.example met placeholders, README: alleen-lezen key, aparte downlink-key, chmod 600, roteren. Key roteren/splitsen in de TTN Console: WACHT-OP-TED (zie Open vragen). |
| F09 | 5 | KLAAR | tests/test_store.py, tests/test_fetch_and_import.py, tests/test_requirements.py::test_readme_documents_retention_and_scheduled_fetch | SQLite-store (data/ 0700, db 0600, idempotente upsert), fetch.py (incrementeel, schrijft alleen bij HTTP 200, --export-tsv met specdecoder), import-snapshots.py. Lokale import: 349 bestanden → 3.998 uniek (port 1: 3.985, 2: 7, 3: 3, 31: 3) = audit. README: 30 dagen retentie, cron + systemd-timer. '7 days'-comment verdwenen. |
| F13 | 5 | TODO | tests/test_ttn.py::test_fetch_uplinks_without_limit_when_number_of_records_is_zero | Deel klaar (fase 4): TTN_NUMBER_OF_RECORDS als int, 0/leeg = geen limit. Rest in fase 5. |
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
- F11: maak in de TTN Console een alleen-lezen key (RIGHT_APPLICATION_TRAFFIC_READ) voor TTN_API_KEY en een aparte downlink-key voor TTN_DOWNLINK_API_KEY. Roteer de huidige key als export-env-vars.sh ooit gedeeld is.

## Vervolg (buiten scope)

## Logboek
- 2026-11-15 17:50 CET start, fase 0 (0.1 bleek al gedaan door commit 358adea)
- 2026-11-15 17:55 CET Fase 0 afgerond
- 2026-11-15 18:05 CET Fase 1 afgerond
- 2026-11-15 18:25 CET Fase 2 afgerond
- 2026-11-15 19:20 CET Fase 3 afgerond (fasecontrole: bitstring uit code/requirements; dry-run 18 downlinks = golden-kolom via tests/test_downlink_encoder.py::test_cli_dry_run_prints_golden_payload)
- 2026-11-15 20:05 CET Fase 4 afgerond (fasecontrole: geen requests.-aanroep buiten oyster3/ttn.py; alle HTTP-tests gemockt incl. 401, timeout, lege respons)
