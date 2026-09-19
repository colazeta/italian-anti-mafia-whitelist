from pathlib import Path

p = Path("src/white_list_archive/parsers/trapani_tables.py")
s = p.read_text(encoding="utf-8")

constant = '''_APPLICANT_CONTINUATIONS = {
    (3, 1, 1): {
        "row": ["", "", "", "", "-Servizi funerari e cimiteriali", "", ""],
        "previous": {"page": 2, "name": "AMG TECH S.R.L.", "identifier": "02303880815"},
    },
    (5, 1, 1): {
        "row": ["", "", "", "", "attività di risanamento e di bonifica e gli altri servizi connessi alla gestione dei rifiuti", "", ""],
        "previous": {"page": 4, "name": "AUTOSPURGHI LICARI S.R.L.", "identifier": "02423440813"},
    },
    (6, 1, 1): {
        "row": ["", "", "", "", "attività di risanamento e di bonifica e gli altri servizi connessi alla gestione dei rifiuti", "", ""],
        "previous": {"page": 5, "name": "AUTOSPURGO PETROSINO DI BIONDO GIUSEPPE", "identifier": "BNDGPP84T14E974C"},
    },
    (7, 1, 1): {
        "row": ["", "", "", "", "-Fornitura di ferro lavorato", "", ""],
        "previous": {"page": 6, "name": "BENENATI BERNARDO", "identifier": "BNNBNR63R14A176Z"},
    },
    (11, 1, 1): {
        "row": ["", "", "", "", "catering", "", ""],
        "previous": {"page": 10, "name": "CIPPONERI LUIGI", "identifier": "CPPLGU81T03G208K"},
    },
    (12, 1, 1): {
        "row": ["", "", "", "", "attività di raccolta, di trasporto nazionale e transfrontaliero, anche per conto terzi, di trattamento e smaltimento dei rifiuti, nonché le attività di risanamento e di bonifica e gli altri servizi connessi alla gestione dei rifiuti", "", ""],
        "previous": {"page": 11, "name": "DA.SCA. S.N.C. DI SCARAMUZZO O. & C. (in Amministrazione Giudiziaria)", "identifier": "01398850816"},
    },
    (15, 1, 1): {
        "row": ["", "", "", "", "-Servizi ambientali, comprese le attività di raccolta, di trasporto nazionale e transfrontaliero, anche per conto terzi, di trattamento e smaltimento dei rifiuti, nonché le attività di risanamento e di bonifica e gli altri servizi connessi alla gestione dei rifiuti", "", ""],
        "previous": {"page": 14, "name": "EUROAMBIENTE S.R.L.", "identifier": "06547530821"},
    },
    (16, 1, 1): {
        "row": ["", "", "", "", "bonifica e gli altri servizi connessi alla gestione dei rifiuti", "", ""],
        "previous": {"page": 15, "name": "EVOLA VITO", "identifier": "VLEVTI60M11F061P"},
    },
    (17, 1, 1): {
        "row": ["", "GOLFO", "", "", "-Nolo a freddo di macchinari -Autotrasporti per conto terzi -Servizi ambientali, comprese le attività di raccolta, di trasporto nazionale e transfrontaliero, anche per conto terzi, di trattamento e smaltimento dei rifiuti, nonché le attività di risanamento e di bonifica e gli altri servizi connessi alla gestione dei rifiuti", "", ""],
        "previous": {"page": 16, "name": "FIAM S.R.L.", "identifier": "02312540814"},
    },
    (18, 1, 1): {
        "row": ["", "", "", "", "bonifica e gli altri servizi connessi alla gestione dei rifiuti", "", ""],
        "previous": {"page": 17, "name": "FILIPPO IMPASTATO & FIGLIO S.N.C.", "identifier": "01578680819"},
    },
    (23, 1, 1): {
        "row": ["", "", "", "", "smaltimento dei rifiuti, nonché le attività di risanamento e di bonifica e gli altri servizi connessi alla gestione dei rifiuti", "", ""],
        "previous": {"page": 22, "name": "LA MARMORA GIUSEPPE", "identifier": "LMRGPP74T06C286Y"},
    },
    (26, 1, 1): {
        "row": ["", "", "", "", "terra e materiali inerti", "", ""],
        "previous": {"page": 25, "name": "MICRON DI PIAZZA DOMENICO", "identifier": "PZZDNC81T24L331M"},
    },
    (30, 1, 1): {
        "row": ["", "", "", "", "attività di risanamento e di bonifica e gli altri servizi connessi alla gestione dei rifiuti", "", ""],
        "previous": {"page": 29, "name": "PANTEL SERVICE S.R.L.", "identifier": "02753100813"},
    },
    (31, 1, 1): {
        "row": ["FILINGERI DI VITO CARLO FILINGERI & C. S.A.S.", "", "", "", "catering", "", ""],
        "previous": {"page": 30, "name": "PASTICCERIA CIOCCOLATTANDO VITO", "identifier": "02883270817"},
    },
    (33, 1, 1): {
        "row": ["", "", "", "", "terra e materiali inerti -Noli a freddo di macchinari", "", ""],
        "previous": {"page": 32, "name": "R.L.G. MONTAGGI S.R.L.", "identifier": "02840470815"},
    },
    (34, 1, 1): {
        "row": ["", "", "", "", "conto terzi, di trattamento e smaltimento dei rifiuti, nonché le attività di risanamento e di bonifica e gli altri servizi connessi alla gestione dei rifiuti", "", ""],
        "previous": {"page": 33, "name": "REAM S.R.L.", "identifier": "02854920812"},
    },
    (35, 1, 1): {
        "row": ["", "", "", "", "attività di risanamento e di bonifica e gli altri servizi connessi alla gestione dei rifiuti", "", ""],
        "previous": {"page": 34, "name": "RENDA S.R.L.", "identifier": "02520400819"},
    },
    (37, 1, 1): {
        "row": ["", "", "", "", "-Autotrasporti per conto di terzi -Servizi ambientali, comprese le attività di raccolta, di trasporto nazionale e transfrontaliero, anche per conto terzi, di trattamento e smaltimento dei rifiuti, nonché le attività di risanamento e di bonifica e gli altri servizi connessi alla gestione dei rifiuti", "", ""],
        "previous": {"page": 36, "name": "SCAME S.R.L.", "identifier": "02281660817"},
    },
    (39, 1, 1): {
        "row": ["", "", "", "", "-Fornitura ferro lavorato -Noli a caldo -Autotrasporto per conto terzi -Servizi ambientali, comprese le attività di raccolta, di trasporto nazionale e transfrontaliero, anche per conto terzi, di trattamento e smaltimento dei rifiuti, nonché le attività di risanamento e di bonifica e gli altri servizi connessi alla gestione dei rifiuti", "", ""],
        "previous": {"page": 38, "name": "SELEMA S.R.L.", "identifier": "02582990814"},
    },
    (40, 1, 1): {
        "row": ["", "", "", "", "attività di raccolta, di trasporto nazionale e transfrontaliero, anche per conto terzi, di trattamento e smaltimento dei rifiuti, nonché le attività di risanamento e di bonifica e gli altri servizi connessi alla gestione dei rifiuti", "", ""],
        "previous": {"page": 39, "name": "SICILSPURGO S.N.C. DI MILAZZO VITO E C.", "identifier": "01615680814"},
    },
    (41, 1, 1): {
        "row": ["", "", "", "", "-Noli a caldo", "", ""],
        "previous": {"page": 40, "name": "SIRTEC S.R.L.", "identifier": "02060960818"},
    },
    (42, 1, 1): {
        "row": ["", "", "", "", "-Autotrasporti conto di terzi", "", ""],
        "previous": {"page": 41, "name": "TRAPANI SCAVI S.R.L.", "identifier": "02696620810"},
    },
    (44, 1, 1): {
        "row": ["SOCIETA' A RESPONSABILITA'LIMITATA", "", "", "", "- Noli a freddo di macchinari - Noli a caldo", "", ""],
        "previous": {"page": 43, "name": "VINCENZO EVOLA CANTIERI MAZARA", "identifier": "02810670816"},
    },
}
'''
if "_APPLICANT_CONTINUATIONS =" not in s:
    anchor = "\n\ndef _clean(value: Any) -> str:\n"
    if s.count(anchor) != 1:
        raise SystemExit("Trapani applicant-continuation constant anchor drift")
    s = s.replace(anchor, "\n\n" + constant + anchor, 1)

old_head = '''def parse_trapani_applicants(path: Path, cfg: dict[str, Any]) -> ParsedBatch:
    rows: list[list[str]] = []
    per_page: list[int] = []
'''
new_head = '''def parse_trapani_applicants(path: Path, cfg: dict[str, Any]) -> ParsedBatch:
    rows: list[list[str]] = []
    row_pages: list[int] = []
    seen_continuations: list[tuple[int, int, int]] = []
    per_page: list[int] = []
'''
if "seen_continuations: list[tuple[int, int, int]]" not in s:
    if s.count(old_head) != 1:
        raise SystemExit("Trapani applicant parser-head anchor drift")
    s = s.replace(old_head, new_head, 1)

old_loop = '''            page_rows: list[list[str]] = []
            for raw in tables[0].extract() or []:
                row = [_clean(value) for value in raw]
                if not any(row) or _is_header(row):
                    continue
                if len(row) != 7 or not row[0] or not _ID_RE.fullmatch(row[3]):
                    raise RuntimeError(f"Trapani applicant row-shape drift on page {page_number}: {row!r}")
                if row[6] not in _ALLOWED_APPLICANT_OUTCOMES:
                    raise RuntimeError(f"Trapani applicant outcome drift on page {page_number}: {row[6]!r}")
                if not _strict_date(row[5]):
                    raise RuntimeError(f"Trapani applicant application-date drift on page {page_number}: {row[5]!r}")
                page_rows.append(row)
            per_page.append(len(page_rows))
            rows.extend(page_rows)
'''
new_loop = '''            page_rows: list[list[str]] = []
            for row_number, raw in enumerate(tables[0].extract() or [], 1):
                row = [_clean(value) for value in raw]
                if not any(row) or _is_header(row):
                    continue
                if len(row) == 7 and row[0] and _ID_RE.fullmatch(row[3]):
                    if row[6] not in _ALLOWED_APPLICANT_OUTCOMES:
                        raise RuntimeError(f"Trapani applicant outcome drift on page {page_number}: {row[6]!r}")
                    if not _strict_date(row[5]):
                        raise RuntimeError(f"Trapani applicant application-date drift on page {page_number}: {row[5]!r}")
                    page_rows.append(row)
                    rows.append(row)
                    row_pages.append(page_number)
                    continue

                key = (page_number, 1, row_number)
                continuation = _APPLICANT_CONTINUATIONS.get(key)
                if continuation is None:
                    raise RuntimeError(f"Trapani applicant row-shape drift on page {page_number}: {row!r}")
                if row != continuation["row"]:
                    raise RuntimeError(f"Trapani applicant continuation evidence drift at {key}: {row!r}")
                previous = continuation["previous"]
                if not rows or row_pages[-1] != previous["page"]:
                    raise RuntimeError(
                        f"Trapani applicant continuation previous-page drift at {key}: "
                        f"{row_pages[-1] if row_pages else None!r}"
                    )
                if rows[-1][0] != previous["name"] or rows[-1][3].upper() != previous["identifier"]:
                    raise RuntimeError(f"Trapani applicant continuation previous-record drift at {key}: {rows[-1]!r}")
                if any(row[index] for index in (2, 3, 5, 6)):
                    raise RuntimeError(f"Trapani applicant continuation unsupported-field drift at {key}: {row!r}")
                for index in (0, 1, 4):
                    if row[index]:
                        rows[-1][index] = _clean(f"{rows[-1][index]} {row[index]}")
                seen_continuations.append(key)
            per_page.append(len(page_rows))
'''
if "continuation = _APPLICANT_CONTINUATIONS.get(key)" not in s:
    if s.count(old_loop) != 1:
        raise SystemExit("Trapani applicant parser-loop anchor drift")
    s = s.replace(old_loop, new_loop, 1)

count_anchor = '''    if per_page != _APPLICANT_ROW_COUNTS:
        raise RuntimeError(f"Trapani applicant per-page row drift: {per_page!r}")
'''
count_repl = count_anchor + '''    if seen_continuations != list(_APPLICANT_CONTINUATIONS):
        raise RuntimeError(f"Trapani applicant continuation-boundary drift: {seen_continuations!r}")
'''
if "applicant continuation-boundary drift" not in s:
    if s.count(count_anchor) != 1:
        raise SystemExit("Trapani applicant continuation-count anchor drift")
    s = s.replace(count_anchor, count_repl, 1)

diag_anchor = '''        "identifier_coverage": sum(bool(record["identifiers"]) for record in records),
        "outcome_counts": dict(Counter(record["outcome_raw"] for record in records)),
'''
diag_repl = '''        "identifier_coverage": sum(bool(record["identifiers"]) for record in records),
        "outcome_counts": dict(Counter(record["outcome_raw"] for record in records)),
        "continuation_rows": len(seen_continuations),
'''
if '"continuation_rows": len(seen_continuations)' not in s:
    if s.count(diag_anchor) != 1:
        raise SystemExit("Trapani applicant diagnostics anchor drift")
    s = s.replace(diag_anchor, diag_repl, 1)

p.write_text(s, encoding="utf-8")
