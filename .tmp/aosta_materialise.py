from pathlib import Path
import json

parser_path = Path('src/white_list_archive/parsers/multi_prefecture_tables.py')
text = parser_path.read_text(encoding='utf-8')
marker = '\n\nPARSERS: dict[str, Callable[[Path, dict[str, Any]], ParsedBatch]] = {'
if 'def parse_aosta_listed' not in text:
    block = r'''


def _aosta_activities(text: str) -> list[str]:
    """Split only explicit source separators while preserving labels such as I-quater."""
    value = _clean(text)
    if not value:
        return []
    parts = [_clean(item) for item in re.split(r"\s+[–—-]\s+", value) if _clean(item)]
    return parts or [value]


def _status_aosta_applicant(outcome: str) -> str:
    folded = _clean(outcome).casefold()
    if "istruttoria" in folded:
        return "pending"
    if "iscritt" in folded:
        return "listed"
    if "negat" in folded or "dinieg" in folded or "rigett" in folded:
        return "rejected_or_denied"
    if "rinunc" in folded or "cancell" in folded or "revoc" in folded:
        return "cancellation_related"
    return "other_or_unknown"


def parse_aosta_listed(path: Path, cfg: dict[str, Any]) -> ParsedBatch:
    records: list[dict[str, Any]] = []
    date_rows = 0
    dropped = 0
    with pdfplumber.open(path) as pdf:
        for _page, row in _table_rows(pdf):
            if len(row) != 8 or not (_DMY_FLEX.fullmatch(row[5] or "") and _DMY_FLEX.fullmatch(row[6] or "")):
                continue
            date_rows += 1
            if not row[0] or not row[3]:
                dropped += 1
                continue
            update = row[7]
            records.append(
                _record(
                    cfg,
                    len(records) + 1,
                    name=row[0],
                    office=row[1],
                    secondary=row[2],
                    identifier_raw=row[3],
                    activities=_aosta_activities(row[4]),
                    status="renewal_update_in_progress" if update else "listed",
                    outcome_raw=update,
                    listing_date=row[5],
                    expiry_date=row[6],
                    primary_date_label="Data iscrizione",
                )
            )
    diagnostics = {
        "parser": "aosta_listed",
        "date_rows": date_rows,
        "public_records": len(records),
        "dropped_date_rows": dropped,
        "status_counts": dict(Counter(record["source_status"] for record in records)),
        "identifier_coverage": sum(bool(record["identifiers"]) for record in records),
    }
    return ParsedBatch(records, diagnostics)


def parse_aosta_applicants(path: Path, cfg: dict[str, Any]) -> ParsedBatch:
    records: list[dict[str, Any]] = []
    date_rows = 0
    dropped = 0
    with pdfplumber.open(path) as pdf:
        for _page, row in _table_rows(pdf):
            if len(row) != 13 or not _DMY_FLEX.fullmatch(row[9] or ""):
                continue
            date_rows += 1
            if not row[0] or not row[5]:
                dropped += 1
                continue
            outcome = row[12]
            records.append(
                _record(
                    cfg,
                    len(records) + 1,
                    name=row[0],
                    office=row[1],
                    secondary=row[3],
                    identifier_raw=row[5],
                    activities=_aosta_activities(row[6]),
                    status=_status_aosta_applicant(outcome),
                    outcome_raw=outcome,
                    application_date=row[9],
                    primary_date_label="Data presentazione istanza",
                )
            )
    diagnostics = {
        "parser": "aosta_applicants",
        "date_rows": date_rows,
        "public_records": len(records),
        "dropped_date_rows": dropped,
        "status_counts": dict(Counter(record["source_status"] for record in records)),
        "identifier_coverage": sum(bool(record["identifiers"]) for record in records),
    }
    return ParsedBatch(records, diagnostics)
'''
    if marker not in text:
        raise SystemExit('PARSERS marker not found')
    text = text.replace(marker, block + marker)
if '"aosta_listed": parse_aosta_listed' not in text:
    old = '    "alessandria_applicants": parse_alessandria_applicants,\n}'
    new = '    "alessandria_applicants": parse_alessandria_applicants,\n    "aosta_listed": parse_aosta_listed,\n    "aosta_applicants": parse_aosta_applicants,\n}'
    if old not in text:
        raise SystemExit('parser map marker not found')
    text = text.replace(old, new)
parser_path.write_text(text, encoding='utf-8')

config_path = Path('data/publication/multi_prefecture_pilot.json')
config = json.loads(config_path.read_text(encoding='utf-8'))
config['verified_at'] = '2026-09-10'
existing = {source['source_key'] for source in config['sources']}
additions = [
    {
        'source_key': 'aosta-listed',
        'parser': 'aosta_listed',
        'authority_key': 'aosta',
        'authority_name': "Regione autonoma Valle d'Aosta · funzioni prefettizie",
        'register_key': 'aosta-ordinary',
        'register_name': 'White List ordinaria',
        'population_scope': 'listed',
        'reference_date': '2026-09-10',
        'source_page_url': 'https://www.regione.vda.it/prefettura/Antimafia/white_list/elenco_imprese_white_list_i.aspx',
        'resource_url': 'https://www.regione.vda.it/allegato.aspx?pk=84307',
        'sha256': '6733bf1e0783f02bb86edfa09155d0625946bd5a1da565704111e98979cccc2f',
        'expected_source_rows': 245,
        'last_source_update': '2026-09-10',
        'last_source_update_basis': 'current official attachment verified on this date; attachment itself is undated',
        'notes': 'The official listed-company page was independently identified and the mutable official attachment was byte-verified on 2026-09-10. The attachment exposes 245 complete source rows with name, identifier, activities, listing date and expiry date; 17 explicitly carry update/renewal text. Rows without a company identity are treated as layout material rather than silently attached to a neighbouring company.'
    },
    {
        'source_key': 'aosta-applicants',
        'parser': 'aosta_applicants',
        'authority_key': 'aosta',
        'authority_name': "Regione autonoma Valle d'Aosta · funzioni prefettizie",
        'register_key': 'aosta-ordinary',
        'register_name': 'White List ordinaria',
        'population_scope': 'applicant',
        'reference_date': '2026-09-10',
        'source_page_url': 'https://www.regione.vda.it/prefettura/Antimafia/white_list/elenco_imprese_richiedenti_i.aspx',
        'resource_url': 'https://www.regione.vda.it/allegato.aspx?pk=84309',
        'sha256': '77d4abb04467d58af4a702e6fec291f19022adff96cfe87b3f88eb929a7f82cd',
        'expected_source_rows': 138,
        'last_source_update': '2026-09-10',
        'last_source_update_basis': 'current official attachment verified on this date; attachment itself is undated',
        'notes': 'The official applicant page and mutable attachment were verified on 2026-09-10. The current attachment contains 138 complete request observations: 116 have a source outcome indicating subsequent White List enrolment and 22 remain in istruttoria. Those outcomes are preserved as source observations; no cross-series entity deduplication is asserted.'
    },
]
for source in additions:
    if source['source_key'] not in existing:
        config['sources'].append(source)
config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

Path('tests/test_aosta_parser_semantics.py').write_text('''from white_list_archive.parsers.multi_prefecture_tables import _aosta_activities, _status_aosta_applicant\n\n\ndef test_aosta_activity_split_preserves_i_quater():\n    assert _aosta_activities("C – D – E – I-quater") == ["C", "D", "E", "I-quater"]\n\n\ndef test_aosta_applicant_source_outcomes_are_not_inferred():\n    assert _status_aosta_applicant("ISCRITTA IN WHITE LIST") == "listed"\n    assert _status_aosta_applicant("IN ISTRUTTORIA") == "pending"\n    assert _status_aosta_applicant("esito non classificato") == "other_or_unknown"\n''', encoding='utf-8')

Path('docs/sources/aosta-operational-check-2026-09-10.md').write_text('''# Aosta operational source check — 2026-09-10\n\n## Authority and official series\n\nIn Valle d’Aosta the President of the Region exercises prefectural functions. The Regione autonoma Valle d’Aosta institutional Prefecture service exposes two distinct White List series: an **Elenco imprese iscritte nella White list** page and an **Elenco imprese richiedenti l’iscrizione** page. Both were reachable during this check and each linked a current official PDF attachment.\n\n## Current official attachments\n\n- Listed: `https://www.regione.vda.it/allegato.aspx?pk=84307` — SHA-256 `6733bf1e0783f02bb86edfa09155d0625946bd5a1da565704111e98979cccc2f`; 49 pages in the 2026-09-10 acquisition; 245 complete source rows with exact listing/expiry dates and a company identifier; 17 rows explicitly carry update/renewal text.\n- Applicants: `https://www.regione.vda.it/allegato.aspx?pk=84309` — SHA-256 `77d4abb04467d58af4a702e6fec291f19022adff96cfe87b3f88eb929a7f82cd`; 21 pages; 138 complete request observations. The source outcome field contains 116 observations indicating subsequent White List enrolment and 22 marked in istruttoria.\n\nThe attachment URLs are stable identifiers and the PDFs themselves do not expose an edition date suitable for a stronger dating claim. Therefore `2026-09-10` is used as the **verified-current/capture reference date**, not as an asserted administrative publication or decision date. The byte hashes, source-row dates and source-page provenance remain the controlling evidence.\n\n## Parser boundary\n\nThe listed parser only accepts rows carrying name, raw identifier, source activities, exact source listing date and exact source expiry date. It maps an explicit update/renewal cell to `renewal_update_in_progress`; otherwise the row remains `listed`, without deriving expiry from the clock. Layout-only table material without company identity is not attached to a neighbouring company.\n\nThe applicant parser only accepts complete 13-column request rows with the source application date and raw identifier. `IN ISTRUTTORIA` maps to `pending`; an explicit source outcome indicating White List enrolment maps to `listed`; negative/cancellation outcomes are mapped only when the corresponding source text is present. The archive remains source-observation based and does not deduplicate applicant outcomes against the listed series as if a canonical LegalEntity had already been established.\n\nNo durable-evidence or canonical-database completion is asserted by this source check.\n''', encoding='utf-8')

workflow = Path('.github/workflows/public-pages.yml')
value = workflow.read_text(encoding='utf-8')
replacements = {
    "assert reg['meta']['record_count'] == 5486": "assert reg['meta']['record_count'] == 5869",
    "{'cosenza','parma','pistoia','bologna','alessandria'}": "{'cosenza','parma','pistoia','bologna','alessandria','aosta'}",
    "'bologna-provincial','bologna-post-sisma','alessandria-ordinary'": "'bologna-provincial','bologna-post-sisma','alessandria-ordinary','aosta-ordinary'",
    "assert reg['meta']['authority_count'] == 5": "assert reg['meta']['authority_count'] == 6",
    "assert reg['meta']['register_count'] == 6": "assert reg['meta']['register_count'] == 7",
    "assert pref['meta']['published_count'] == 5": "assert pref['meta']['published_count'] == 6",
}
for old, new in replacements.items():
    if old not in value:
        raise SystemExit(f'public-pages marker missing: {old}')
    value = value.replace(old, new)
anchor = "          assert len(alessandria) == 1 and alessandria[0]['mapped'] and alessandria[0]['published']\n"
if "jurisdiction_name'] == 'Aosta'" not in value:
    if anchor not in value:
        raise SystemExit('Aosta workflow assertion anchor missing')
    value = value.replace(anchor, anchor + "          aosta = [x for x in pref['prefectures'] if x['jurisdiction_name'] == 'Aosta']\n          assert len(aosta) == 1 and aosta[0]['mapped'] and aosta[0]['published']\n")
workflow.write_text(value, encoding='utf-8')

browser = Path('tests/public_portal_browser.cjs')
value = browser.read_text(encoding='utf-8')
label_old = "      assert.ok(labels.includes('White List ordinaria · Prefettura di Alessandria'));"
if 'funzioni prefettizie' not in value:
    if label_old not in value:
        raise SystemExit('browser label anchor missing')
    value = value.replace(label_old, label_old + "\n      assert.ok(labels.includes(\"White List ordinaria · Regione autonoma Valle d'Aosta · funzioni prefettizie\"));")
if '      assert.equal(stats.total,5486);' not in value:
    raise SystemExit('browser total marker missing')
value = value.replace('      assert.equal(stats.total,5486);', '      assert.equal(stats.total,5869);')
previous_old = "      const previous=registry.records.filter(r=>r.authority_key!=='alessandria');"
if previous_old not in value:
    raise SystemExit('browser previous marker missing')
value = value.replace(previous_old, "      const previous=registry.records.filter(r=>!['alessandria','aosta'].includes(r.authority_key));")
a_anchor = "      assert.equal(alessandria.filter(r=>r.source_key==='alessandria-applicants').length,71);\n"
if "source_key==='aosta-listed'" not in value:
    if a_anchor not in value:
        raise SystemExit('browser Aosta anchor missing')
    value = value.replace(a_anchor, a_anchor + "      const aosta=registry.records.filter(r=>r.authority_key==='aosta');\n      assert.equal(aosta.length,383);\n      assert.equal(aosta.filter(r=>r.source_key==='aosta-listed').length,245);\n      assert.equal(aosta.filter(r=>r.source_key==='aosta-applicants').length,138);\n      assert.deepEqual(statusCounts(aosta),{listed:344,pending:22,renewal_update_in_progress:17});\n")
browser.write_text(value, encoding='utf-8')
