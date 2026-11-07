from datetime import date
from uuid import uuid4

import pytest

from white_list_archive.semantic import canonicalise
from white_list_archive.semantic.combined_whitelist_v1 import (
    EditionAttributionRequired, ProjectionSelectionRequired, _parse_run_contexts,
    validate_input_selection,
)

RUN, CAPTURE, EDITION, REGISTER = [str(uuid4()) for _ in range(4)]


def row(run=RUN, edition=EDITION):
    return (run, 'interpretation', edition, 'edition', date(2026, 8, 3), REGISTER)


class Cursor:
    def __init__(self, rows, unattributed=False):
        self.rows, self.unattributed, self.statements = rows, unattributed, []
    def execute(self, statement, params):
        self.statements.append((statement, params))
    def fetchone(self):
        return (self.unattributed,)
    def fetchall(self):
        return self.rows


@pytest.mark.parametrize('parse,capture', [(RUN, None), (None, CAPTURE), ('bad', CAPTURE)])
def test_invalid_pin_fails_before_any_database_access(parse, capture):
    cur = Cursor([])
    with pytest.raises(ValueError):
        _parse_run_contexts(cur, 'series', parse_run_id=parse, capture_id=capture)
    assert cur.statements == []


def test_explicit_pair_returns_only_its_context_despite_unrelated_unattributed_input():
    cur = Cursor([row()], unattributed=True)
    contexts = _parse_run_contexts(cur, 'series', parse_run_id=RUN, capture_id=CAPTURE)
    assert len(contexts) == 1 and contexts[0]['capture_id'] == CAPTURE
    assert contexts[0]['parse_run_id'] == RUN
    assert cur.statements[0][1] == ('series', RUN, CAPTURE)


@pytest.mark.parametrize('rows,error', [([], ProjectionSelectionRequired),
    ([row(edition=None)], EditionAttributionRequired),
    ([row(), row(edition=str(uuid4()))], ProjectionSelectionRequired)])
def test_pinned_pair_requires_one_existing_attribution(rows, error):
    with pytest.raises(error):
        _parse_run_contexts(Cursor(rows), 'series', parse_run_id=RUN, capture_id=CAPTURE)


@pytest.mark.parametrize('rows', [[row(), row(run=str(uuid4()))],
                                [row(), row(edition=str(uuid4()))]])
def test_unpinned_mixed_interpretations_or_editions_fail_closed(rows):
    with pytest.raises(ProjectionSelectionRequired):
        _parse_run_contexts(Cursor(rows), 'series')


def test_unpinned_unambiguous_legacy_context_is_preserved():
    assert _parse_run_contexts(Cursor([row()]), 'series')[0]['parse_run_id'] == RUN
    assert validate_input_selection() is None


def test_canonical_loaders_apply_same_selection_to_entities_identifiers_and_procedures():
    cur = Cursor([])
    selected = [RUN]
    canonicalise._load_observations(cur, 'series', projection_run_ids=selected)
    canonicalise._load_eligible_procedures(cur, 'series', projection_run_ids=selected)
    assert len(cur.statements) == 3
    for statement, params in cur.statements:
        assert 'eo.projection_run_id=ANY(%s::uuid[])' in statement
        assert params == ('series', selected, selected)


def test_current_pipeline_canonicalises_only_returned_projection_ids(monkeypatch):
    from types import SimpleNamespace
    from white_list_archive.semantic import pipeline_current as pipeline
    calls = []
    class ContextCursor:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
    conn = SimpleNamespace(cursor=lambda: ContextCursor())
    monkeypatch.setattr(pipeline.base, '_series_context', lambda *a, **kw:
                        {'series_id': 'series-id', 'fingerprints': ['fixture']})
    family = SimpleNamespace(code='fixture', implementation_module='fixture',
        parser_version='1', record_contract_code='fixture', field_locator_prefix='fixture:')
    monkeypatch.setattr(pipeline.base, '_select_family', lambda *a:
                        SimpleNamespace(family=family, selection_basis='explicit'))
    monkeypatch.setattr(pipeline, 'semantic_profile_for_family', lambda *a, **kw:
                        SimpleNamespace(projector_module='fixture', code='fixture', projector_version='2'))
    def validate(*args, **kwargs):
        assert kwargs == {'parse_run_id': RUN, 'capture_id': CAPTURE}
        calls.append('validate')
    def project(*args, **kwargs):
        assert kwargs == {'parse_run_id': RUN, 'capture_id': CAPTURE}
        calls.append('project')
        return {'projection_run_ids': [RUN]}
    monkeypatch.setattr(pipeline.importlib, 'import_module', lambda name:
                        SimpleNamespace(_parse_run_contexts=validate, project_series=project))
    def mappings(*args):
        calls.append('mappings')
        return {}
    monkeypatch.setattr(pipeline.base, 'ensure_field_mappings', mappings)
    def canonical(*args, **kwargs):
        assert kwargs == {'projection_run_ids': [RUN]}
        calls.append('canonical')
        return {}
    monkeypatch.setattr(pipeline, 'canonicalise_series', canonical)
    monkeypatch.setattr(pipeline, '_clear_legacy_address_country_assumption',
                        lambda *a: pytest.fail('Pinned projection must not mutate unrelated legacy addresses'))
    result = pipeline.run_pipeline(conn, 'series', parse_run_id=RUN, capture_id=CAPTURE)
    assert result['input_selection'] == {'parse_run_id': RUN, 'capture_id': CAPTURE}
    assert calls == ['validate', 'project', 'mappings', 'canonical']
