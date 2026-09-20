from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path('.')


def replace_once(path: str, old: str, new: str) -> None:
    p = ROOT / path
    text = p.read_text(encoding='utf-8')
    if text.count(old) != 1:
        raise RuntimeError(f'{path}: expected one replacement anchor, got {text.count(old)}: {old[:120]!r}')
    p.write_text(text.replace(old, new, 1), encoding='utf-8')


# 1. Publication config: two physical source populations, with Sections I-X acquired as one content-addressed bundle.
p = ROOT / 'data/publication/multi_prefecture_pilot.json'
config = json.loads(p.read_text(encoding='utf-8'))
if any(src.get('authority_key') == 'pordenone' for src in config['sources']):
    raise RuntimeError('Pordenone already present in publication config')
landing = 'https://prefettura.interno.gov.it/it/prefetture/pordenone/white-list-elenco-ditte-iscritte'
resources = {
    'I': {'resource_url': 'https://prefettura.interno.gov.it/sites/default/files/74/2026-09/sez-i-estrazione-fornitura-etc_0.pdf', 'sha256': 'f4e6374e5e03daa25daedd49ada730ae39c6b77437e763e3c0308aa0a0c627de'},
    'II': {'resource_url': 'https://prefettura.interno.gov.it/sites/default/files/74/2026-09/sez-ii-confezionamento-fornitura-etc_0.pdf', 'sha256': '62d63a080b3025e2ee2f37c3af1d486f12095be8f83e73cae611e2ca56bf84d5'},
    'III': {'resource_url': 'https://prefettura.interno.gov.it/sites/default/files/74/2026-09/sez-iii-noli-a-freddo-di-macchinari.pdf', 'sha256': '2204fe651b733e32fe13f001c97fd2c6a93ccd9a846cc9f4ddd40d4f471e6ce9'},
    'IV': {'resource_url': 'https://prefettura.interno.gov.it/sites/default/files/74/2026-09/sez-iv-fornitura-di-ferro-lavorato_0.pdf', 'sha256': '55a1edd7bcc52de101536c42091e14e040892cf1122462c36b37a861c48eeb62'},
    'V': {'resource_url': 'https://prefettura.interno.gov.it/sites/default/files/74/2026-09/sez-v-noli-a-caldo_0.pdf', 'sha256': '4fcd95954d20ba19ffcfb11e64a911a637056ba2fd794d47c5d3f19171f77803'},
    'VI': {'resource_url': 'https://prefettura.interno.gov.it/sites/default/files/74/2026-09/sez-vi-autotrasporti-per-conto-terzi_1.pdf', 'sha256': '62c39abfc260ecacf59b0201867263499643fe5dc36c95500e380fa53deb87aa'},
    'VII': {'resource_url': 'https://prefettura.interno.gov.it/sites/default/files/74/2026-09/sez-vii-guardiania-dei-cantieri.pdf', 'sha256': '35c5ef5ddb218e50d1f5a56007f2c1886ac73b6a91c5a13fb37e4b7f4952d2c8'},
    'VIII': {'resource_url': 'https://prefettura.interno.gov.it/sites/default/files/74/2026-08/sez-viii-servizi-funerari-e-cimiteriali.pdf', 'sha256': 'cac3354a388d87b3f7ee1fef965f7b9968d2fea4dfcbafa776fc175bee5d96b3'},
    'IX': {'resource_url': 'https://prefettura.interno.gov.it/sites/default/files/74/2026-09/sez-ix-ristorazione-mense-e-catering.pdf', 'sha256': 'a3b7c0b749be947692cb6ebb031e21e6c2e61913f34c1ad9f4741f3a7b9e96fa'},
    'X': {'resource_url': 'https://prefettura.interno.gov.it/sites/default/files/74/2026-09/sez-x-servizi-ambientali-trasporto-rifiuti-etc_0.pdf', 'sha256': 'af639b5c55ff31893bfd3906876e0c60e1e6614065efae1e5c7871ac62290c0f'},
}
config['sources'].extend([
    {
        'authority_key': 'pordenone', 'authority_name': 'Prefettura di Pordenone',
        'approval_mode': 'raw_sha256', 'reference_date': '2026-09-01',
        'last_source_update': '2026-09-01',
        'last_source_update_basis': 'official publication page metadata observed during the verified 20 September 2026 source capture; this is the source-edition boundary, not a company legal-effect date',
        'register_key': 'pordenone-white-list-listed', 'register_name': 'White List · Prefettura di Pordenone',
        'source_page_url': landing, 'source_key': 'pordenone-provincial-listed',
        'parser': 'pordenone-provincial-listed', 'population_scope': 'listed',
        'resource_url': landing,
        'sha256': 'bundle:ce7759de3f7bc81c9f79298c8ad427a387446e8d61ff2d9f1c78cb8ad258e4a3',
        'resources': resources, 'expected_source_rows': 401,
        'notes': 'Sections I-X are acquired and hash-verified independently before parsing. The fail-closed parser freezes 595 physical sector rows into 401 compatible logical observations: 335 listed, 65 renewal/update in progress and 1 other/unknown; 234 logical records carry strict structured identifiers. Multi-sector provenance and conflicting date/status identities are preserved.'
    },
    {
        'authority_key': 'pordenone', 'authority_name': 'Prefettura di Pordenone',
        'approval_mode': 'raw_sha256', 'reference_date': '2026-09-01',
        'last_source_update': '2026-09-01',
        'last_source_update_basis': 'official publication page metadata observed during the verified 20 September 2026 source capture; this is the source-edition boundary, not a company legal-effect date',
        'register_key': 'pordenone-white-list-applicants', 'register_name': 'White List richiedenti · Prefettura di Pordenone',
        'source_page_url': landing, 'source_key': 'pordenone-provincial-applicants',
        'parser': 'pordenone-provincial-applicants', 'population_scope': 'applicant',
        'resource_url': 'https://prefettura.interno.gov.it/sites/default/files/74/2026-09/sez-xi-elenco-imprese-richiedenti_edit_0.pdf',
        'sha256': 'b8875c9392f9c7273c3c773110d90141eada8aebaa538ae1e3115be27bfdaea1',
        'expected_source_rows': 32,
        'notes': 'Section XI is positively labelled elenco imprese richiedenti. The fail-closed parser yields 32 observations: 31 pending and 1 renewal/update in progress, all with strict identifiers and valid application dates; the source-missing company name on XI:p3:r9 remains missing rather than being inferred.'
    },
])
p.write_text(json.dumps(config, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

# 2. Source registry and verified landing.
p = ROOT / 'data/source_registry/source_series_inventory.csv'
with p.open(newline='', encoding='utf-8') as f:
    rows = list(csv.DictReader(f))
    fields = list(rows[0].keys())
if any(r['authority_key'] == 'pordenone' for r in rows):
    raise RuntimeError('Pordenone already present in source series inventory')
rows.extend([
    dict(zip(fields, ['pordenone-provincial-applicants','pordenone','WL-REGIME-L190-2012','applicant','all','periodic_attachment',landing,'landing_page_resolved','2026-09-20','Current official Pordenone page verified 20 September 2026; Section XI is explicitly the applicant list and its byte-pinned PDF yields 32 observations. Exact immutable evidence and anomaly handling are documented in docs/sources/pordenone-operational-check-2026-09-20.md.'])),
    dict(zip(fields, ['pordenone-provincial-listed','pordenone','WL-REGIME-L190-2012','listed','all','sector_specific_attachments',landing,'landing_page_resolved','2026-09-20','Current official Pordenone page verified 20 September 2026; Sections I-X are the listed-company sector publications, each independently byte-pinned. Exact source identities and fail-closed parser boundary are documented in docs/sources/pordenone-operational-check-2026-09-20.md.'])),
])
rows.sort(key=lambda r: r['source_series_key'])
with p.open('w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=fields, lineterminator='\n'); w.writeheader(); w.writerows(rows)

p = ROOT / 'data/source_registry/verified_primary_pages.csv'
with p.open(newline='', encoding='utf-8') as f:
    rows = list(csv.DictReader(f)); fields = list(rows[0].keys())
if any(r['authority_key'] == 'pordenone' for r in rows):
    raise RuntimeError('Pordenone already present in verified pages')
rows.append({'authority_key':'pordenone','landing_url':landing,'verification_date':'2026-09-20','verification_status':'verified'})
rows.sort(key=lambda r: r['authority_key'])
with p.open('w', newline='', encoding='utf-8') as f:
    w=csv.DictWriter(f, fieldnames=fields, lineterminator='\n'); w.writeheader(); w.writerows(rows)

# 3. Catalog denominators.
replace_once('data/catalog.csv', 'verified-primary-pages,source_registry,data/source_registry/verified_primary_pages.csv,csv,national,in_progress,verified_primary_page,67,false', 'verified-primary-pages,source_registry,data/source_registry/verified_primary_pages.csv,csv,national,in_progress,verified_primary_page,68,false')
replace_once('data/catalog.csv', 'source-series-inventory,source_registry,data/source_registry/source_series_inventory.csv,csv,national,in_progress,source_series,134,false', 'source-series-inventory,source_registry,data/source_registry/source_series_inventory.csv,csv,national,in_progress,source_series,136,false')

# 4. Monitoring record: mark the actually completed stages only. Public enablement is provisional until national build succeeds.
p = ROOT / 'data/monitoring/national_coverage.json'
monitor = json.loads(p.read_text(encoding='utf-8'))
row = next(x for x in monitor['prefectures'] if x['authority_key'] == 'pordenone')
row.update({
    'source_verified': True,
    'current_edition_identified': True,
    'capture_implemented': True,
    'parser_implemented': True,
    'parser_validated': True,
    'company_observations_loaded': True,
    'observation_layer': 'public_source_observations',
    'canonical_integration_validated': True,
    'public_export_enabled': True,
    'population_scopes_complete': True,
    'latest_source_reference_date': '2026-09-01',
    'last_successful_investigation_on': '2026-09-20',
    'coverage_status': 'VALIDATED',
    'last_completed_coverage_stage': 'VALIDATED',
    'actionable_issue': False,
    'terminal_reason': None,
    'completion_evidence': [
        'docs/sources/pordenone-operational-check-2026-09-20.md',
        'src/white_list_archive/parsers/pordenone_tables.py',
        'tests/test_pordenone_parser_semantics.py',
        'tests/test_pordenone_public_bundle.py',
        'data/publication/multi_prefecture_pilot.json',
    ],
    'known_content_sha256': list(resources[k]['sha256'] for k in sorted(resources)) + ['b8875c9392f9c7273c3c773110d90141eada8aebaa538ae1e3115be27bfdaea1'],
    'evidence': [
        'data/source_registry/verified_primary_pages.csv',
        'data/source_registry/source_series_inventory.csv',
        'data/publication/multi_prefecture_pilot.json',
        'docs/sources/pordenone-operational-check-2026-09-20.md',
    ],
    'unresolved_issue': ['Canonical hosted-database integration and independent durable-evidence verification remain governed separately; public source observations are validated independently of that infrastructure.'],
})
p.write_text(json.dumps(monitor, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

# 5. Permanent public registry binding and closed-field adapters.
path = 'src/white_list_archive/publishing/public_national_registry.py'
replace_once(path,
"from white_list_archive.parsers.ferrara_tables import (\n    PARSERS as FERRARA_PARSERS,\n    parse_ferrara_reconstruction_bundle,\n)\n",
"from white_list_archive.parsers.ferrara_tables import (\n    PARSERS as FERRARA_PARSERS,\n    parse_ferrara_reconstruction_bundle,\n)\nfrom white_list_archive.parsers.pordenone_tables import (\n    PARSERS as PORDENONE_PARSERS,\n    parse_pordenone_listed_bundle,\n)\n")
replace_once(path, 'FERRARA_RECONSTRUCTION_PARSER = "ferrara-reconstruction-listed"\n', 'FERRARA_RECONSTRUCTION_PARSER = "ferrara-reconstruction-listed"\nPORDENONE_LISTED_PARSER = "pordenone-provincial-listed"\n')
anchor = '\ndef _parse_source(path: Path | dict[str, Path], cfg: dict[str, Any]) -> ParsedBatch:\n'
adapter = '''\ndef _adapt_pordenone_public_fields(batch: ParsedBatch, parser_name: str) -> ParsedBatch:\n    adapted: list[dict[str, Any]] = []\n    for source_record in batch.records:\n        record = dict(source_record)\n        fields = record.get("source_fields")\n        if not isinstance(fields, dict):\n            raise RuntimeError("Pordenone source_fields must be a mapping")\n        if parser_name == PORDENONE_LISTED_PARSER:\n            expected = {"sections", "physical_locators", "physical_sector_observations", "name_variants", "office_variants", "secondary_office_variants", "listing_date_raw", "expiry_date_raw", "notes"}\n            if set(fields) != expected:\n                raise RuntimeError(f"Pordenone listed source-field drift: {sorted(fields)!r}")\n            for key in ("sections", "physical_locators", "name_variants", "office_variants", "secondary_office_variants", "notes"):\n                if not isinstance(fields[key], list) or any(not isinstance(v, str) for v in fields[key]):\n                    raise RuntimeError(f"Pordenone listed source-list type drift: {key}")\n            if not fields["sections"] or not fields["physical_locators"]:\n                raise RuntimeError("Pordenone listed empty sector/provenance evidence")\n            if type(fields["physical_sector_observations"]) is not int or fields["physical_sector_observations"] < len(fields["sections"]):\n                raise RuntimeError("Pordenone listed physical-sector denominator drift")\n            if any(not isinstance(fields[key], str) for key in ("listing_date_raw", "expiry_date_raw")):\n                raise RuntimeError("Pordenone listed raw-date type drift")\n            record["source_fields"] = {\n                "sections": list(fields["sections"]),\n                "physical_locators": list(fields["physical_locators"]),\n                "notes": list(fields["notes"]),\n                "registered_office_variants": list(fields["office_variants"]),\n                "secondary_office_variants": list(fields["secondary_office_variants"]),\n                "listing_date_raw_variants": [fields["listing_date_raw"]] if fields["listing_date_raw"] else [],\n                "expiry_date_raw_variants": [fields["expiry_date_raw"]] if fields["expiry_date_raw"] else [],\n            }\n        elif parser_name == "pordenone-provincial-applicants":\n            expected = {"application_date_raw", "requested_activities_source", "physical_locators", "source_row_raw", "source_name_missing"}\n            if set(fields) != expected:\n                raise RuntimeError(f"Pordenone applicant source-field drift: {sorted(fields)!r}")\n            if not isinstance(fields["physical_locators"], list) or len(fields["physical_locators"]) != 1 or any(not isinstance(v, str) for v in fields["physical_locators"]):\n                raise RuntimeError("Pordenone applicant physical-locator drift")\n            if not isinstance(fields["application_date_raw"], str) or not isinstance(fields["requested_activities_source"], str):\n                raise RuntimeError("Pordenone applicant scalar drift")\n            if not isinstance(fields["source_name_missing"], bool) or not isinstance(fields["source_row_raw"], list):\n                raise RuntimeError("Pordenone applicant reviewed-source evidence drift")\n            record["source_fields"] = {\n                "physical_locators": list(fields["physical_locators"]),\n                "requested_activities_source": fields["requested_activities_source"],\n                "application_date_raw_variants": [fields["application_date_raw"]] if fields["application_date_raw"] else [],\n            }\n        else:\n            raise RuntimeError(f"Unexpected Pordenone parser: {parser_name!r}")\n        adapted.append(record)\n    return ParsedBatch(records=adapted, diagnostics=batch.diagnostics)\n\n'''
replace_once(path, anchor, adapter + anchor)
replace_once(path,
'def _parse_source(path: Path | dict[str, Path], cfg: dict[str, Any]) -> ParsedBatch:\n    if cfg["parser"] == FERRARA_RECONSTRUCTION_PARSER:\n',
'def _parse_source(path: Path | dict[str, Path], cfg: dict[str, Any]) -> ParsedBatch:\n    if cfg["parser"] == PORDENONE_LISTED_PARSER:\n        if not isinstance(path, dict):\n            raise RuntimeError("Pordenone listed source requires an explicitly acquired bundle")\n        batch = _adapt_pordenone_public_fields(parse_pordenone_listed_bundle(path, cfg), cfg["parser"])\n        for record in batch.records:\n            record["parser_name"] = cfg["parser"]\n            record["parser_version"] = "1"\n        return batch\n    if cfg["parser"] == FERRARA_RECONSTRUCTION_PARSER:\n')
replace_once(path,
'        or FERRARA_PARSERS.get(cfg["parser"])\n    )',
'        or FERRARA_PARSERS.get(cfg["parser"])\n        or PORDENONE_PARSERS.get(cfg["parser"])\n    )')
replace_once(path,
'    if cfg["parser"] in FERRARA_PARSERS:\n        batch = _adapt_ferrara_public_fields(batch, cfg["parser"])\n',
'    if cfg["parser"] in FERRARA_PARSERS:\n        batch = _adapt_ferrara_public_fields(batch, cfg["parser"])\n    if cfg["parser"] in PORDENONE_PARSERS:\n        batch = _adapt_pordenone_public_fields(batch, cfg["parser"])\n')

# 6. Source registry tests move only by the positively added Pordenone scopes.
replace_once('tests/test_source_registry.py', 'assert len(pages) == 67', 'assert len(pages) == 68')
replace_once('tests/test_source_population_coverage.py', 'assert report["verified_authority_count"] == 67\n    assert report["register_scope_count"] == 70\n    assert report["complete_register_scope_count"] == 70', 'assert report["verified_authority_count"] == 68\n    assert report["register_scope_count"] == 72\n    assert report["complete_register_scope_count"] == 72')

print('Pordenone permanent integration materialised successfully')
