#!/usr/bin/env python3
"""Research discovery ledger; source discovery never certifies flow completeness."""
from __future__ import annotations
import argparse
import csv
import hashlib
import io
import json
import subprocess
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
VERSION = '0.2.0'
ORDINARY = 'WL-REGIME-L190-2012'
FIELDS = ['authority_key', 'regime_code', 'scope_key', 'pilot_stage', 'source_series_count',
          'listed_discovered', 'applicant_discovered', 'both_populations_discovered',
          'canonical_ingestion_review', 'application_date_signal', 'outcome_signal',
          'processing_time_eligibility', 'snapshot_pending_age_eligibility',
          'clearance_rate_eligibility', 'total_backlog_eligibility', 'reason']
INPUTS = ['data/source_registry/territorial_authorities.csv',
          'data/source_registry/source_series_inventory.csv',
          'research/white_list_performance_pilot/config/pilot_authorities.csv']


def read_csv(path):
    with path.open(encoding='utf-8', newline='') as handle:
        return list(csv.DictReader(handle))


def assess(authorities, series, pilot):
    """Keep ordinary/special registers separate; never infer absence from discovery."""
    configs = {row['authority_key']: row for row in pilot}
    known = {row['authority_key'] for row in authorities}
    if len(known) != len(authorities):
        raise ValueError('Duplicate authority keys')
    grouped = defaultdict(list)
    for row in series:
        if row['authority_key'] not in known:
            raise ValueError('Unresolved authority in source inventory')
        if not row.get('regime_code'):
            raise ValueError('Source regime missing')
        grouped[(row['authority_key'], row['regime_code'])].append(row)
    keys = set(grouped) | {(key, ORDINARY) for key in known}
    rows = []
    for authority, regime in sorted(keys):
        source_rows = grouped.get((authority, regime), [])
        populations = {row['population_scope'] for row in source_rows}
        listed = bool(populations & {'listed', 'listed_and_applicant'})
        applicant = bool(populations & {'applicant', 'listed_and_applicant'})
        cfg = configs.get(authority, {})
        applicable = regime == ORDINARY
        app = cfg.get('application_date_signal', 'unknown') if applicable else 'unknown'
        outcome = cfg.get('outcome_signal', 'unknown') if applicable else 'unknown'
        canonical = cfg.get('canonical_ingestion_ready', 'unknown') if applicable else 'unknown'
        rows.append({
            'authority_key': authority, 'regime_code': regime,
            'scope_key': authority + '::' + regime,
            'pilot_stage': cfg.get('pilot_stage', 'expansion_pool'),
            'source_series_count': len(source_rows),
            'listed_discovered': 'yes' if listed else 'unresolved',
            'applicant_discovered': 'yes' if applicant else 'unresolved',
            'both_populations_discovered': 'yes' if listed and applicant else 'unresolved',
            'canonical_ingestion_review': 'candidate_for_validation' if canonical == 'yes' else 'not_verified_for_research',
            'application_date_signal': app, 'outcome_signal': outcome,
            'processing_time_eligibility': 'not_verified_same_procedure_and_date_semantics',
            'snapshot_pending_age_eligibility': 'candidate_for_row_validation' if applicant and app == 'yes' else 'not_verified',
            'clearance_rate_eligibility': 'not_verified_inflows_all_outcomes_and_window',
            'total_backlog_eligibility': 'not_verified_full_pending_population',
            'reason': 'Discovery is not completeness of administrative applications or outcomes'
        })
    return rows


def render(rows):
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=FIELDS, lineterminator='\n')
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue()


def main():
    cli = argparse.ArgumentParser()
    cli.add_argument('--output', type=Path, required=True,
                     help='Explicit destination; frozen v0.1 outputs are never overwritten by default')
    cli.add_argument('--check', action='store_true')
    args = cli.parse_args()
    rows = assess(*(read_csv(ROOT / path) for path in INPUTS))
    text = render(rows)
    if args.check:
        if not args.output.exists() or args.output.read_text() != text:
            raise SystemExit('Research discovery ledger differs from the requested file')
        return
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(text, encoding='utf-8')
    metadata = {'analysis_version': VERSION,
                'code_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                'source_sha256': {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in INPUTS},
                'output_sha256': hashlib.sha256(text.encode()).hexdigest(),
                'scope_count': len(rows),
                'both_populations_discovered': sum(r['both_populations_discovered'] == 'yes' for r in rows),
                'flow_eligible_scopes': 0}
    args.output.with_suffix('.metadata.json').write_text(json.dumps(metadata, indent=2) + '\n')
    print(json.dumps(metadata))

if __name__ == '__main__':
    main()
