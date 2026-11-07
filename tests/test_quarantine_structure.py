import csv
import json
from pathlib import Path

import pytest

from white_list_archive.acquisition.quarantine_structure import inspect_quarantined_structure
from white_list_archive.acquisition.auto_transform import (
    EditionReviewRequired, _require_edition_review,
)


def test_lodi_reports_observed_structure_without_exposing_source_values(tmp_path):
    path = tmp_path / "source.csv"
    rows = [
        ["private-title", "", "", "", "", "", ""],
        ["private-company", "private-address", "", "private-identifier", "", "", ""],
        ["Sezione I", "", "", "", "", "", ""],
        ["short-private-row"],
        ["Ragione sociale", "", "", "", "Data iscrizione", "", ""],
    ]
    with path.open('w', newline='') as handle:
        csv.writer(handle).writerows(rows)
    report = inspect_quarantined_structure(path, "lodi_listed")
    assert report['inspection_completed']
    assert report['physical_rows'] == 5
    assert report['seven_column_rows'] == 4
    assert report['other_width_rows'] == 1
    assert report['section_marker_rows'] == 1
    assert report['reviewed_header_position_matches'] == 1
    assert report['reviewed_section_position_matches'] == 1
    assert not report['reviewed_physical_row_count_matches']
    assert report['source_reference_date'] is None
    assert 'private' not in json.dumps(report)
    assert 'Ragione' not in json.dumps(report)
    assert all(isinstance(v, (bool, int)) or v is None for v in report.values())


def test_milano_uses_physical_tables_without_emitting_rows(tmp_path):
    path = tmp_path / 'source.html'
    path.write_text('<table><tr><td>private-heading</td></tr>'
                    '<tr><td>private-header</td></tr>'
                    '<tr><td>private-company</td><td>x</td><td>x</td><td>x</td><td>x</td><td>x</td></tr>'
                    '<tr><td>private-malformed-row</td></tr></table>')
    report = inspect_quarantined_structure(path, 'milano_combined')
    assert report['inspection_completed']
    assert report['source_tables'] == 1
    assert report['six_column_data_rows'] == 1
    assert report['other_width_data_rows'] == 1
    assert not report['reviewed_table_count_matches']
    assert 'private' not in json.dumps(report)
    assert all(isinstance(v, (bool, int)) or v is None for v in report.values())


def test_failed_encoding_does_not_leak_exception_or_weaken_quarantine(tmp_path):
    path = tmp_path / 'bad.csv'
    path.write_bytes(b'private-company,\xff')
    report = inspect_quarantined_structure(path, 'lodi_applicants')
    assert not report['inspection_completed']
    assert not report['edition_approval']
    assert not report['parser_compatibility_approved']
    assert 'private' not in json.dumps(report)
    progress = {}
    with pytest.raises(EditionReviewRequired):
        _require_edition_review(path, 'lodi_applicants', progress)
    assert progress['structural_inspection'] == report


def test_even_matching_structure_never_approves_edition(tmp_path):
    path = tmp_path / 'applicants.csv'
    path.write_text('\n'.join(','.join(['private'] * 7) for _ in range(10)))
    progress = {}
    with pytest.raises(EditionReviewRequired):
        _require_edition_review(path, 'lodi_applicants', progress)
    report = progress['structural_inspection']
    assert report['inspection_completed']
    assert report['reviewed_physical_row_count_matches']
    assert not report['edition_approval']
    assert not report['parser_compatibility_approved']
    assert report['source_reference_date'] is None


def test_quarantine_diagnostics_are_persisted_privately_but_excluded_from_public_report(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from white_list_archive.acquisition import auto_transform as worker
    from white_list_archive.storage import evidence

    cfg = {'source_key': 'lodi-applicants', 'authority_key': 'lodi',
           'resource_url': 'https://official.example/source.csv', 'sha256': '1' * 64,
           'parser': 'lodi_applicants', 'reference_date': '2026-09-21'}
    state = {'schema_version': 1, 'robots': {'lodi': {
        'population_mapping_reviewed': True, 'resources': {cfg['resource_url']: {'capture_history': [{
            'source_key': 'lodi-applicants', 'capture_id': 'capture',
            'sha256': '2' * 64, 'byte_size': 10, 'captured_at': '2026-11-07T00:00:00Z',
        }]}}
    }}}
    state_path, config_path = tmp_path / 'state.json', tmp_path / 'config.json'
    state_path.write_text(json.dumps(state))
    config_path.write_text(json.dumps({'sources': [cfg]}))
    path = tmp_path / 'source.csv'
    path.write_text('private-company\n')
    monkeypatch.setenv('EVIDENCE_DATABASE_URL', 'not-emitted')
    monkeypatch.setattr(evidence.StoreConfig, 'from_env', lambda: SimpleNamespace())
    monkeypatch.setattr(evidence, 'client_for', lambda config: None)
    monkeypatch.setattr(evidence, 'EvidenceStore', lambda *args: object())

    def inspect_and_quarantine(job, **kwargs):
        _require_edition_review(path, 'lodi_applicants', kwargs['progress'])

    saved_private = []
    monkeypatch.setattr(worker, 'transform_one', inspect_and_quarantine)
    monkeypatch.setattr(worker, 'persist_operational_report', lambda store, report: saved_private.append(report))
    private_path, public_path = tmp_path / 'private.json', tmp_path / 'public.json'
    assert worker.main(['--state', str(state_path), '--source-config', str(config_path),
                        '--report', str(private_path), '--public-report', str(public_path),
                        '--code-revision', 'a' * 40]) == 1
    private = json.loads(private_path.read_text())
    outcome = private['outcomes'][0]
    assert outcome['status'] == 'quarantined'
    assert outcome['reason'] == 'edition_bound_parser_requires_review'
    assert outcome['structural_inspection']['physical_rows'] == 1
    assert saved_private[0]['outcomes'][0] == outcome
    assert private['transformed'] == 0
    assert private['publications'] == 0
    assert 'structural_inspection' not in public_path.read_text()
    assert 'private-company' not in private_path.read_text()
