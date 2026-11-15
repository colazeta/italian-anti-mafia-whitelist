from datetime import datetime, timezone

import pytest

from white_list_archive.acquisition.production_checkpoint import collect_checkpoint


class Cursor:
    def __init__(self, denied=(), snapshot_mismatches=1, input_mismatches=0):
        self.calls = []
        self.result = None
        self.denied = set(denied)
        self.snapshot_mismatches = snapshot_mismatches
        self.input_mismatches = input_mismatches

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def execute(self, sql, params=None):
        self.calls.append((sql, params))
        if "transaction_timestamp()" in sql:
            self.result = (datetime(2026, 11, 7, tzinfo=timezone.utc),)
        elif "has_schema_privilege" in sql:
            self.result = (params[0] != "semantic" and params[1] not in self.denied,)
        elif "sum(record_count)" in sql:
            self.result = (13473, self.snapshot_mismatches)
        elif "count(DISTINCT c.series_id)" in sql:
            self.result = (27, 19)
        elif "FROM source.capture_parse_run cp" in sql:
            self.result = (self.input_mismatches,)
        elif "storage_status_code" in sql:
            self.result = (14,)
        else:
            self.result = (38,)

    def fetchone(self):
        return self.result


class Connection:
    def __init__(self, **kwargs):
        self.cur = Cursor(**kwargs)

    def cursor(self):
        return self.cur


def test_unreadable_layer_is_unknown_and_never_queried_as_zero():
    conn = Connection()
    report = collect_checkpoint(conn, code_revision="a" * 40)
    assert report["metrics"]["semantic_observations"]["value"] is None
    assert report["metrics"]["semantic_observations"]["status"] == "not_verified"
    assert not any("FROM semantic.entity_observation" in q for q, _ in conn.cur.calls)
    assert conn.cur.calls[0][0] == "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"
    assert report["metrics"]["snapshot_record_occurrences"]["distinct_business_count"] is False
    assert report["metrics"]["snapshot_count_mismatches"]["numerator"] == 1
    assert report["metrics"]["snapshot_count_mismatches"]["denominator"] == 38
    assert report["independent_backup_verified"] is None
    assert report["release_approval_verified"] is None


def test_bad_revision_stops_before_database_access():
    conn = Connection()
    with pytest.raises(ValueError):
        collect_checkpoint(conn, code_revision="main")
    assert conn.cur.calls == []


def test_conversion_counts_use_captures_and_registered_series_as_distinct_denominators():
    report = collect_checkpoint(Connection(), code_revision='a' * 40)
    metrics = report['metrics']
    assert metrics['capture_interpretation_coverage']['numerator'] == 27
    assert metrics['capture_interpretation_coverage']['denominator'] == 38
    assert metrics['series_interpretation_coverage']['numerator'] == 19
    assert metrics['series_interpretation_coverage']['denominator'] == 38
    assert metrics['parse_run_snapshot_coverage']['numerator'] == 38
    assert metrics['parse_run_snapshot_coverage']['denominator'] == 38
    assert metrics['capture_parse_input_mismatches']['numerator'] == 0
    assert metrics['capture_parse_input_mismatches']['denominator'] == 38
    assert metrics['capture_parse_input_mismatches']['integrity_status'] == 'passed'
    assert metrics['snapshot_count_mismatches']['integrity_status'] == 'failed'


@pytest.mark.parametrize('table', ['source_capture', 'capture_parse_run', 'parse_run_input', 'parse_snapshot'])
def test_missing_relational_reader_is_unknown_and_does_not_execute_join(table):
    conn = Connection(denied=[table])
    metrics = collect_checkpoint(conn, code_revision='a' * 40)['metrics']
    for key in ('capture_interpretation_coverage', 'series_interpretation_coverage', 'capture_parse_input_mismatches'):
        assert metrics[key]['status'] == 'not_verified'
        assert metrics[key]['numerator'] is None
    assert not any('FROM source.capture_parse_run cp' in q or 'count(DISTINCT c.series_id)' in q
                   for q, _ in conn.cur.calls)


def test_missing_series_denominator_cannot_be_reported_as_verified_coverage():
    metrics = collect_checkpoint(Connection(denied=['source_series']), code_revision='a' * 40)['metrics']
    assert metrics['capture_interpretation_coverage']['status'] == 'verified'
    assert metrics['series_interpretation_coverage']['status'] == 'not_verified'
    assert metrics['series_interpretation_coverage']['denominator'] is None


@pytest.mark.parametrize('mismatches,exit_code', [(0, 0), (1, 1)])
@pytest.mark.parametrize('mismatch_kind', ['snapshot', 'labelled_input'])
def test_cli_persists_integrity_findings_before_failing_without_disclosing_report(
        monkeypatch, capsys, mismatches, exit_code, mismatch_kind):
    import json
    from contextlib import contextmanager
    from white_list_archive.acquisition import production_checkpoint as checkpoint
    from white_list_archive.storage import evidence

    @contextmanager
    def connection(dsn):
        yield Connection(snapshot_mismatches=mismatches if mismatch_kind == 'snapshot' else 0,
                         input_mismatches=mismatches if mismatch_kind == 'labelled_input' else 0)
    monkeypatch.setenv('EVIDENCE_DATABASE_URL', 'private-test-dsn')
    monkeypatch.setattr(checkpoint, 'private_connection', connection)
    monkeypatch.setattr(evidence.StoreConfig, 'from_env', lambda: object())
    monkeypatch.setattr(evidence, 'client_for', lambda cfg: object())
    monkeypatch.setattr(evidence, 'EvidenceStore', lambda client, cfg: object())
    reports = []
    monkeypatch.setattr(checkpoint, 'persist_operational_report', lambda store, report: reports.append(report))
    assert checkpoint.main(['--code-revision', 'a' * 40]) == exit_code
    assert len(reports) == 1
    safe = json.loads(capsys.readouterr().out)
    assert safe['checkpoint_persisted'] is True
    assert safe['failed_integrity_checks'] == mismatches
    assert safe['publications'] == 0
    assert set(safe) == {'checkpoint_persisted', 'verified_metrics', 'unverified_metrics',
                         'failed_integrity_checks', 'publications'}
