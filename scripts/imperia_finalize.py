from __future__ import annotations

import csv
import json
import re
from pathlib import Path

ROOT = Path('.')
LANDING = 'https://prefettura.interno.gov.it/it/prefetture/imperia/evidenza/white-list'
LISTED_URL = 'https://prefettura.interno.gov.it/sites/default/files/46/2026-09/elenco-ditte-iscritte-white-list_3.xlsx'
APPLICANT_URL = 'https://prefettura.interno.gov.it/sites/default/files/46/2026-08/elenco-delle-ditte-che-hanno-presentato-istanza-di-iscrizione-nelle-white-lists_2.doc'
LISTED_SHA = '9716cf0571946f5e39d90b177c41e7919957eb88adb71cf22fd928b73c615a3f'
APPLICANT_SHA = 'e1c93ece7e919e1b3f7c6cf2cd399e7585bcef5e7713876b0a9662de642b60f9'


def read_csv(path: str):
    p = ROOT / path
    with p.open(encoding='utf-8', newline='') as f:
        r = csv.DictReader(f)
        return r.fieldnames, list(r)


def write_csv(path: str, fields, rows):
    p = ROOT / path
    with p.open('w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator='\n')
        w.writeheader(); w.writerows(rows)


# Verified landing page.
fields, rows = read_csv('data/source_registry/verified_primary_pages.csv')
assert not any(r['authority_key'] == 'imperia' for r in rows)
rows.append({'authority_key':'imperia','landing_url':LANDING,'verification_date':'2026-09-19','verification_status':'verified'})
rows.sort(key=lambda r: r['authority_key'])
write_csv('data/source_registry/verified_primary_pages.csv', fields, rows)

# Current source series: both populations are positively exposed by the current landing.
fields, rows = read_csv('data/source_registry/source_series_inventory.csv')
assert not any(r['authority_key'] == 'imperia' for r in rows)
rows.extend([
    {
        'source_series_key':'imperia-applicants','authority_key':'imperia','regime_code':'WL-REGIME-L190-2012',
        'population_scope':'applicant','sector_scope':'all','publication_model':'periodic_attachment','series_url':LANDING,
        'resource_resolution_status':'landing_page_resolved','verified_date':'2026-09-19',
        'notes':'Current official Imperia landing directly reverified 19 September 2026 and positively exposes the applicant legacy Word attachment under the label ELENCO DITTE CHE HANNO PRESENTATO ISTANZA DI ISCRIZIONE. Two independent cache-bypassed captures were byte-identical at SHA-256 '+APPLICANT_SHA+'. The reviewed table yields 131 observations: 117 source-explicit subsequent enrolments, 6 pending, 5 cancellation-related and 3 other/unknown; no applicant population or legal status is inferred from absence.'
    },
    {
        'source_series_key':'imperia-listed','authority_key':'imperia','regime_code':'WL-REGIME-L190-2012',
        'population_scope':'listed','sector_scope':'all','publication_model':'periodic_attachment','series_url':LANDING,
        'resource_resolution_status':'landing_page_resolved','verified_date':'2026-09-19',
        'notes':'Current official Imperia landing directly reverified 19 September 2026 and positively exposes the listed-company XLSX under the label ELENCO DELLE DITTE ISCRITTE WL. Two independent cache-bypassed captures were byte-identical at SHA-256 '+LISTED_SHA+'. Conservative repeated-section grouping yields 142 observations from 246 section rows: 105 listed and 37 renewal/update in progress.'
    }
])
rows.sort(key=lambda r: r['source_series_key'])
write_csv('data/source_registry/source_series_inventory.csv', fields, rows)

# Publication configuration.
p = ROOT/'data/publication/multi_prefecture_pilot.json'
config = json.loads(p.read_text(encoding='utf-8'))
assert not any(s['authority_key'] == 'imperia' for s in config['sources'])
common = {
    'authority_key':'imperia','authority_name':'Prefettura di Imperia','register_key':'imperia-ordinary',
    'register_name':'White List ordinaria','reference_date':'2026-09-18','source_page_url':LANDING,
    'last_source_update':'2026-09-18',
    'last_source_update_basis':"official landing-page 'Ultimo aggiornamento' 18 September 2026, 10:54; reference_date preserves that explicit publication-surface update date and is not promoted to a company decision/legal-effect date",
    'approval_mode':'raw_sha256',
}
config['sources'].extend([
    {**common,'source_key':'imperia-listed','parser':'imperia_listed','population_scope':'listed','resource_url':LISTED_URL,'sha256':LISTED_SHA,'expected_source_rows':142,'expected_sector_rows':246,'notes':'Official current listed XLSX. 246 section rows group only on source-visible identity, addresses, identifier, dates and update/status evidence to 142 observations: 105 listed and 37 renewal/update in progress. Structured identifier coverage is 131/142. Two malformed listing-date tokens (07/07/206 and 06/07/206 at logical-observation level) remain raw with normalised date blank.'},
    {**common,'source_key':'imperia-applicants','parser':'imperia_applicants','population_scope':'applicant','resource_url':APPLICANT_URL,'sha256':APPLICANT_SHA,'expected_source_rows':131,'notes':'Official current applicant legacy Word table positively exposed by the current landing. 337 physical table rows resolve to 131 observations after exact repeated-header/blank/activity-continuation handling: 117 explicit subsequent enrolments, 6 pending, 5 cancellation-related and 3 other/unknown. Structured identifier coverage is 126/131; two malformed application-date tokens remain raw.'},
])
p.write_text(json.dumps(config, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')

# Coverage state: validated source/parser/public candidate, with infrastructure gates kept distinct.
p = ROOT/'data/monitoring/national_coverage.json'
coverage = json.loads(p.read_text(encoding='utf-8'))
entry = next(x for x in coverage['prefectures'] if x['authority_key'] == 'imperia')
assert entry['coverage_status'] == 'SOURCE_IDENTIFIED' and not entry['public_export_enabled']
entry.update({
    'source_verified':True,'current_edition_identified':True,'capture_implemented':True,'parser_implemented':True,
    'parser_validated':True,'company_observations_loaded':True,'observation_layer':'public_source_observations',
    'canonical_integration_validated':False,'public_export_enabled':True,'durable_evidence_verified':False,
    'population_scopes_complete':True,'latest_source_reference_date':'2026-09-18',
    'last_successful_investigation_on':'2026-09-19','coverage_status':'VALIDATED','actionable_issue':False,
    'completion_evidence':['docs/sources/imperia-operational-check-2026-09-19.md','src/white_list_archive/parsers/imperia_sources.py','tests/test_imperia_parser_semantics.py','data/publication/multi_prefecture_pilot.json'],
    'known_content_sha256':[LISTED_SHA,APPLICANT_SHA],
    'evidence':['data/source_registry/verified_primary_pages.csv','data/source_registry/source_series_inventory.csv','data/publication/multi_prefecture_pilot.json','docs/sources/imperia-operational-check-2026-09-19.md'],
    'unresolved_issue':['Canonical hosted-database integration and independent durable-evidence verification remain separate infrastructure gates. The applicant attachment is a legacy Word file whose HTTP Last-Modified predates the current landing update; no attachment metadata is promoted to an edition, company-decision or legal-effect date.'],
    'last_completed_coverage_stage':'VALIDATED',
})
p.write_text(json.dumps(coverage, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')

# Catalogue denominators.
fields, rows = read_csv('data/catalog.csv')
for row in rows:
    if row['dataset_id'] == 'verified-primary-pages':
        assert row['record_count'] == '59'; row['record_count'] = '60'
    if row['dataset_id'] == 'source-series-inventory':
        assert row['record_count'] == '116'; row['record_count'] = '118'
write_csv('data/catalog.csv', fields, rows)

# Wire parser into public builder.
p = ROOT/'src/white_list_archive/publishing/public_national_registry.py'
text = p.read_text(encoding='utf-8')
needle = 'from white_list_archive.parsers.grosseto_openxml import PARSERS as GROSSETO_PARSERS\n'
assert needle in text and 'IMPERIA_PARSERS' not in text
text = text.replace(needle, needle+'from white_list_archive.parsers.imperia_sources import PARSERS as IMPERIA_PARSERS\n', 1)
needle = '        or GROSSETO_PARSERS.get(cfg["parser"])\n'
assert needle in text
text = text.replace(needle, needle+'        or IMPERIA_PARSERS.get(cfg["parser"])\n', 1)
p.write_text(text, encoding='utf-8')

# Create reviewed public workflow candidate; promotion is deliberately separate because workflow-file writes require elevated scope.
src = (ROOT/'.github/workflows/public-pages.yml').read_text(encoding='utf-8')
assert "      - 'src/white_list_archive/parsers/grosseto_openxml.py'" in src
src = src.replace("      - 'src/white_list_archive/parsers/grosseto_openxml.py'", "      - 'src/white_list_archive/parsers/grosseto_openxml.py'\n      - 'src/white_list_archive/parsers/imperia_sources.py'", 1)
assert "assert reg['meta']['record_count'] == 64592" in src
src = src.replace("assert reg['meta']['record_count'] == 64592", "assert reg['meta']['record_count'] == 64865", 1)
assert "assert reg['meta']['authority_count'] == 59" in src
assert "assert reg['meta']['register_count'] == 61" in src
assert "assert pref['meta']['published_count'] == 59" in src and "assert pref['meta']['mapped_count'] == 59" in src
src = src.replace("assert reg['meta']['authority_count'] == 59", "assert reg['meta']['authority_count'] == 60", 1)
src = src.replace("assert reg['meta']['register_count'] == 61", "assert reg['meta']['register_count'] == 62", 1)
src = src.replace("assert pref['meta']['published_count'] == 59", "assert pref['meta']['published_count'] == 60", 1)
src = src.replace("assert pref['meta']['mapped_count'] == 59", "assert pref['meta']['mapped_count'] == 60", 1)
# Extend exact authority/register sets rather than replacing their whole literals.
needle = ",'grosseto'}"
assert needle in src
src = src.replace(needle, ",'grosseto','imperia'}", 1)
needle = ",'grosseto-ordinary'\n          }"
assert needle in src
src = src.replace(needle, ",'grosseto-ordinary','imperia-ordinary'\n          }", 1)
# Add exact Imperia assertions immediately after Grosseto block.
anchor = "          assert len({r['record_locator'] for r in grosseto_records}) == 418\n"
assert anchor in src
checks = """          imperia = [x for x in pref['prefectures'] if x['authority_key'] == 'imperia']
          assert len(imperia) == 1 and imperia[0]['mapped'] and imperia[0]['published'] and imperia[0]['series_count'] == 2
          imperia_records = [r for r in reg['records'] if r['authority_key'] == 'imperia']
          assert len(imperia_records) == 273
          assert sum(r['source_key'] == 'imperia-listed' for r in imperia_records) == 142
          assert sum(r['source_key'] == 'imperia-applicants' for r in imperia_records) == 131
          assert sum(r['source_status'] == 'listed' for r in imperia_records) == 222
          assert sum(r['source_status'] == 'pending' for r in imperia_records) == 6
          assert sum(r['source_status'] == 'renewal_update_in_progress' for r in imperia_records) == 37
          assert sum(r['source_status'] == 'cancellation_related' for r in imperia_records) == 5
          assert sum(r['source_status'] == 'other_or_unknown' for r in imperia_records) == 3
          assert sum(bool(r['identifiers']) for r in imperia_records) == 257
          assert len({r['record_locator'] for r in imperia_records}) == 273
"""
src = src.replace(anchor, anchor+checks, 1)
Path('tmp').mkdir(exist_ok=True)
(ROOT/'tmp/imperia-public-pages-candidate.yml').write_text(src, encoding='utf-8')

# Operational evidence note.
doc = ROOT/'docs/sources/imperia-operational-check-2026-09-19.md'
doc.write_text('''# Imperia White List operational check — 19 September 2026

## Official publication surface

The current official Prefettura di Imperia White List landing page positively exposes two distinct current populations: **ELENCO DELLE DITTE ISCRITTE WL** and **ELENCO DITTE CHE HANNO PRESENTATO ISTANZA DI ISCRIZIONE**. The landing metadata states **Ultimo aggiornamento: 18 September 2026, 10:54**. This is positive population evidence; no applicant population is inferred from search failure or absence. The publication configuration preserves 18 September as the explicit landing update/reference boundary only and does not promote it to a company decision or legal-effect date.

## Content-addressed evidence

Two independent cache-bypassed GETs for each current attachment were byte-identical. The listed XLSX is **86,337 bytes**, SHA-256 `'''+LISTED_SHA+'''`; the applicant legacy Word document is **635,392 bytes**, SHA-256 `'''+APPLICANT_SHA+'''`. The applicant file's HTTP Last-Modified predates the current landing update and is retained only as transport metadata, not as a substantive edition date. Publication remains fail-closed on the exact approved hashes.

## Reviewed parser boundary

The listed workbook has ten White List section sheets plus legend/empty support sheets and **246 company-section rows**. Rows are grouped only where source-visible company identity, legal/secondary offices, source identifier, raw/normalised dates and update/status evidence agree, yielding **142 observations: 105 listed and 37 renewal/update in progress**. Structured identifier coverage is **131/142**. Source listing-date tokens `07/07/206` and `06/07/206` are retained raw with normalised dates blank; no repair is inferred.

The applicant legacy Word table is parsed through `antiword` into one frozen seven-column table with **337 physical rows**: 68 repeated headers, 13 blank rows, 125 activity-continuation rows and **131 logical observations**. Status is assigned only from positive source evidence: **117 listed** where the source explicitly says `Iscritta ...`, **6 pending** from exact `In corso`, **5 cancellation-related** from explicit cancellation wording, and **3 other/unknown** where the outcome is blank or a bare unlabelled date. Structured identifier coverage is **126/131**. Two malformed application-date tokens (`25/0720522`, `10/1\\0/2024`) remain raw and unnormalised. All 117 explicit subsequent-enrolment outcome dates remain source-derived and parseable.

The resulting Imperia candidate contains **273 observations** with **257 structured identifiers**. The two populations share one ordinary provincial register; they are separate source series, not separate legal registers.
''', encoding='utf-8')

print('Imperia permanent integration materialised; workflow candidate at tmp/imperia-public-pages-candidate.yml')
