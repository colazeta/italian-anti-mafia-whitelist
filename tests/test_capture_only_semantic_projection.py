import pytest

from white_list_archive.semantic.combined_whitelist_v1 import (
    EditionAttributionRequired, _parse_run_contexts, project_series,
)


class Cursor:
    def __init__(self):
        self.statements = []
    def __enter__(self):
        return self
    def __exit__(self, *args):
        pass
    def execute(self, statement, params):
        self.statements.append((statement, params))
    def fetchone(self):
        return (True,)


def test_capture_only_candidate_fails_before_projection_context_or_writes():
    cur = Cursor()
    with pytest.raises(EditionAttributionRequired, match='source-edition attribution'):
        _parse_run_contexts(cur, 'synthetic-series')
    assert len(cur.statements) == 1
    statement, params = cur.statements[0]
    assert params == ('synthetic-series',)
    assert 'NOT EXISTS' in statement
    assert 'source.capture_edition' in statement
    assert 'e.series_id=s.series_id' in statement
    assert not any(keyword in statement for keyword in ('INSERT', 'UPDATE', 'DELETE'))


def test_direct_projection_cannot_return_empty_success_for_capture_only_input():
    cur = Cursor()
    class Connection:
        def cursor(self):
            return cur
    with pytest.raises(EditionAttributionRequired):
        project_series(Connection(), 'synthetic-series')
    assert len(cur.statements) == 1
