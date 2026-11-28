import json

import pytest

from white_list_archive.acquisition import release_readiness as readiness
from test_biella_parser_semantics import _source_html


def test_explicit_date_keeps_page_update_separate_from_capture_and_ignores_scripts():
    raw = b'<script>Ultimo aggiornamento 30 dicembre 2029</script><p>Ultimo aggiornamento</p><time>6 novembre 2026, 12:00</time>'
    assert readiness.explicit_update_date(raw, '2026-11-15T12:00:00Z') == '2026-11-06'
    assert readiness.explicit_update_date('Ultimo aggiornamento Giovedì 12 Novembre 2026, ore 10:49'.encode(),
                                         '2026-11-15T12:00:00Z') == '2026-11-12'


@pytest.mark.parametrize('text', [
    'No declared source date', 'Ultimo aggiornamento 31 febbraio 2026',
    'Ultimo aggiornamento 16 novembre 2026',
    'Ultimo aggiornamento 3 novembre 2026 Ultimo aggiornamento 4 novembre 2026',
    'Ultimo aggiornamento Lunedì 12 Novembre 2026',
])
def test_missing_invalid_ambiguous_future_dates_fail_closed(text):
    with pytest.raises(ValueError):
        readiness.explicit_update_date(text.encode(), '2026-11-15T12:00:00Z')


@pytest.mark.parametrize('declaration', [
    'Ultimo aggiornamento 6 novembre 20260',
    'Ultimo aggiornamento 6 novembre 2026extra',
    'Ultimo aggiornamento 6 novembre 2026/27',
    'Ultimo aggiornamento 6 novembre 2026-2027',
    'Ultimo aggiornamento 6 novembre 2026.5',
    'Ultimo aggiornamento 15/11/2026',
    'Ultimo aggiornamento non disponibile',
    'Ultimo aggiornamento',
])
@pytest.mark.parametrize('valid_first', [False, True])
def test_partial_or_uninterpretable_declarations_are_never_ignored(declaration, valid_first):
    text = ('Ultimo aggiornamento 6 novembre 2026 ' if valid_first else '') + declaration
    with pytest.raises(ValueError):
        readiness.explicit_update_date(text.encode(), '2026-11-15T12:00:00Z')


def test_repeated_explicit_dates_must_agree_and_all_weekdays_must_be_valid():
    text = '<p>Ultimo aggiornamento: Giovedì 12 Novembre 2026, ore 10:49</p>'
    text += '<p>Ultimo aggiornamento 12 novembre 2026.</p>'
    assert readiness.explicit_update_date(text.encode(), '2026-11-15T12:00:00Z') == '2026-11-12'
    with pytest.raises(ValueError):
        readiness.explicit_update_date(text.replace('12 novembre 2026.', '13 novembre 2026.').encode(),
                                      '2026-11-15T12:00:00Z')
    with pytest.raises(ValueError):
        readiness.explicit_update_date(text.encode(), '2026-11-15T12:00:00')


@pytest.mark.parametrize('changed_populations', [(), ('listed',), ('applicant',), ('listed', 'applicant')])
def test_cli_readiness_uses_both_latest_populations_even_if_unchanged(
        tmp_path, monkeypatch, capsys, changed_populations):
    from copy import deepcopy
    from test_auto_transform import _scalar, _history, H1, H2
    from white_list_archive.storage import evidence

    state, config = _scalar()
    template = config['sources'][0]
    config['sources'] = []
    state['robots'] = {'biella': {'population_mapping_reviewed': True, 'resources': {}}}
    for population in ('listed', 'applicant'):
        source = {**deepcopy(template), 'source_key': 'biella-' + population,
                  'authority_key': 'biella', 'population_scope': population,
                  'resource_url': 'https://official.example/' + population}
        config['sources'].append(source)
        old = _history(source['source_key'], H1, 'old-' + population)
        latest = _history(source['source_key'], H2 if population in changed_populations else H1,
                          'latest-' + population, '2026-11-12T12:00:00Z')
        state['robots']['biella']['resources'][source['resource_url']] = {'capture_history': [old, latest]}
    state_path, config_path = tmp_path/'state.json', tmp_path/'config.json'
    state_path.write_text(json.dumps(state))
    config_path.write_text(json.dumps(config))
    monkeypatch.setattr(evidence.StoreConfig, 'from_env', lambda: object())
    monkeypatch.setattr(evidence, 'client_for', lambda cfg: object())
    monkeypatch.setattr(evidence, 'EvidenceStore', lambda client, cfg: object())
    inspected = []
    def inspect(job, store):
        inspected.append((job['source_key'], job['captures']['primary']['state']['capture_id']))
        return {'source_key': job['source_key'], 'status': 'source_candidate_requires_review',
                'publication_approved': False}
    monkeypatch.setattr(readiness, 'inspect_job', inspect)
    reports = []
    monkeypatch.setattr(readiness.transform, 'persist_operational_report', lambda store, report: reports.append(report))
    assert readiness.main(['--state', str(state_path), '--source-config', str(config_path)]) == 0
    assert set(inspected) == {('biella-' + p, 'latest-' + p) for p in ('listed', 'applicant')}
    assert reports[0]['results'][0]['status'] == 'review_metadata_ready'
    summary = json.loads(capsys.readouterr().out)
    assert summary['approvals'] == summary['publications'] == 0


def test_biella_census_accounts_for_every_row_and_rejects_silently_skipped_widths(tmp_path):
    path = tmp_path/'source.html'
    path.write_text(_source_html())
    assert readiness.biella_complete_physical_rows(path, 'listed') == 10
    assert readiness.biella_complete_physical_rows(path, 'applicant') == 3
    # The legacy parser skips this 3-cell row. Readiness must quarantine it.
    text = _source_html().replace('</table>', '<tr><td>unknown source row</td><td>details</td><td>123</td></tr></table>', 1)
    path.write_text(text)
    with pytest.raises(ValueError, match='Unclassified'):
        readiness.biella_complete_physical_rows(path, 'applicant')


@pytest.mark.parametrize('population', ['listed', 'applicant'])
def test_como_independent_census_preserves_source_counter_discrepancy_and_rejects_skipped_rows(tmp_path, population):
    from white_list_archive.parsers import como_html as family
    from test_como_parser_semantics import _write
    applicant = population == 'applicant'
    title = family._APPLICANT_TITLE if applicant else family._LISTED_TITLE
    header = family._APPLICANT_HEADER if applicant else family._LISTED_HEADER
    label = 'NUMERO AZIENDE IN FASE ISCRIZIONE:' if applicant else 'NUMERO AZIENDE ISCRITTE:'
    rows = [[title, '', '', '', '', '', '', ''], [label, '0', '', '', '', '', '', ''], list(header),
            ['SYNTHETIC COMPANY', 'COMO', '', '', '', 'Sez. I', '', 'nov-26' if applicant else '']]
    path = _write(tmp_path, 'source.html', rows)
    assert readiness.como_complete_physical_rows(path, population) == 1  # Source counter remains zero.
    path = _write(tmp_path, 'source.html', rows + [['unclassified', 'details', '123']])
    with pytest.raises(ValueError, match='Unclassified'):
        readiness.como_complete_physical_rows(path, population)
    path = _write(tmp_path, 'source.html', rows + [['', '', '', 'unclassified note', '', '', '', '']])
    with pytest.raises(ValueError, match='Unclassified'):
        readiness.como_complete_physical_rows(path, population)


def test_authorities_and_populations_are_independent_and_never_approved():
    jobs = [{'source_key': a+'-'+p, 'config': {'authority_key': a, 'population_scope': p}}
            for a in ('biella', 'como') for p in ('listed', 'applicant')]
    def inspect(job):
        if job['source_key'] == 'biella-listed': raise ValueError('private source data')
        return {'source_key': job['source_key'], 'status': 'source_candidate_requires_review', 'publication_approved': False}
    report = readiness.triage(jobs, inspect)
    assert [r['status'] for r in report['results']] == ['requires_source_review', 'review_metadata_ready', 'incomplete_population_inputs']
    assert report['approvals'] == report['publications'] == 0
    assert 'private source data' not in json.dumps(report)


def test_public_readiness_is_closed_against_private_diagnostics_and_messages():
    report = {'kind': 'archived-release-readiness', 'results': [{'authority_key': 'biella', 'status': 'review_metadata_ready', 'sources': [{
        'source_key': 'biella-listed', 'status': 'source_candidate_requires_review', 'publication_approved': False,
        'private_text': 'sensitive fixture', 'public_records_sha256': 'sensitive fixture',
        'blank_names': 'sensitive fixture', 'diagnostics': {'sector_rows': 10, 'rows': ['sensitive fixture'],
        'identifier_coverage': 'sensitive fixture', 'status_counts': {'listed': 3, 'sensitive fixture': 2}}}]}]}
    safe = readiness.public_summary(report)
    assert 'sensitive fixture' not in json.dumps(safe)
    assert safe['results'][0]['sources'][0]['quality_counts'] == {'sector_rows': 10}
    assert safe['publications'] == safe['approvals'] == 0


def test_source_inspection_uses_verified_original_and_never_reuses_old_date(monkeypatch):
    from test_biella_parser_semantics import _cfg
    import hashlib
    raw = (_source_html() + '<p>Ultimo aggiornamento Giovedì 12 Novembre 2026, ore 10:49</p>').encode()
    sha = hashlib.sha256(raw).hexdigest()
    cfg = {**_cfg('listed'), 'parser': 'biella_html_listed', 'expected_source_rows': 8}
    job = {'source_key': 'biella-listed', 'config': cfg,
           'captures': {'primary': {'url': cfg['resource_url'], 'state': {'sha256': sha}}}}
    monkeypatch.setattr(readiness.transform, '_verified_capture', lambda store, entry: (
        {'sha256': sha, 'byte_size': len(raw), 'captured_at': '2026-11-15T12:00:00Z'}, {}, raw))
    result = readiness.inspect_job(job, object())
    assert result['records'] == 9 and result['physical_rows'] == 10
    assert result['reference_date'] == '2026-11-12'
    assert result['previous_reference_date'] == '2026-08-26'
    assert result['previous_edition_qa_differences'] == ['source_row_count_changed']
    assert result['publication_approved'] is False
    assert result['original_and_capture_provenance_verified'] is True


def _taranto_census_fixture(population):
    from white_list_archive.parsers import taranto_html as family
    from html import escape
    header = family._LISTED_HEADER if population == "listed" else family._APPLICANT_HEADER
    cells = (["EXAMPLE COMPANY", "TARANTO", "01234567890", "01/09/2026", "01/09/2027", "I", ""]
             if population == "listed" else
             ["EXAMPLE COMPANY", "TARANTO", "01234567890", "I", "01/09/2026"])
    header_html = "<tr>" + "".join("<th>" + escape(v) + "</th>" for v in header) + "</tr>"
    company_html = "<tr>" + "".join("<td>" + escape(v) + "</td>" for v in cells) + "</tr>"
    return "<table><tr><td>layout<table>" + header_html + company_html + "</table></td></tr></table>"


@pytest.mark.parametrize("population", ["listed", "applicant"])
def test_taranto_independent_census_counts_physical_rows_without_parser_filter(tmp_path, population):
    path = tmp_path / "taranto.html"
    html = _taranto_census_fixture(population)
    path.write_text(html)
    assert readiness.taranto_complete_physical_rows(path, population) == 1
    from white_list_archive.parsers import taranto_html as family
    assert len(family._find_rows(family._tables(path), applicant=population == "applicant")) == 1


@pytest.mark.parametrize("population", ["listed", "applicant"])
@pytest.mark.parametrize("kind", ["row_width", "missing_name", "pre_header", "header_drift", "repeated_header"])
def test_taranto_independent_census_quarantines_unclassified_physical_content(tmp_path, population, kind):
    from white_list_archive.parsers import taranto_html as family
    from html import escape
    html = _taranto_census_fixture(population)
    width = 7 if population == "listed" else 5
    if kind == "row_width":
        row = "<tr><td>EXTRA</td><td>UNREVIEWED</td></tr>"
        html = html.replace("</table>", row + "</table>", 1)
    elif kind == "missing_name":
        row = "<tr><td></td>" + "<td>UNREVIEWED</td>" * (width - 1) + "</tr>"
        html = html.replace("</table>", row + "</table>", 1)
    elif kind == "pre_header":
        html = html.replace("<table><tr><th>", "<table><tr><td>UNREVIEWED</td></tr><tr><th>", 1)
    elif kind == "header_drift":
        # A second header-like row with an unexpected schema must be rejected.
        row = "<tr><th>Ragione sociale</th><th>UNREVIEWED</th></tr>"
        html = html.replace("</table>", row + "</table>", 1)
    else:
        header = family._LISTED_HEADER if population == "listed" else family._APPLICANT_HEADER
        row = "<tr>" + "".join("<th>" + escape(v) + "</th>" for v in header) + "</tr>"
        html = html.replace("</table>", row + "</table>", 1)
    path = tmp_path / "taranto.html"
    path.write_text(html)
    with pytest.raises(ValueError, match="Taranto"):
        readiness.taranto_complete_physical_rows(path, population)


def test_taranto_census_never_promotes_source_observations(monkeypatch, tmp_path):
    from test_taranto_html import _cfg
    import hashlib
    cfg = {**_cfg("listed"), "parser": "taranto_html_listed", "expected_source_rows": 99}
    raw = (_taranto_census_fixture("listed") + "<p>Ultimo aggiornamento 6 novembre 2026</p>").encode()
    sha = hashlib.sha256(raw).hexdigest()
    job = {"source_key": "taranto-listed", "config": cfg,
           "captures": {"primary": {"url": cfg["resource_url"], "state": {"sha256": sha}}}}
    monkeypatch.setattr(readiness.transform, "_verified_capture", lambda store, entry: (
        {"sha256": sha, "byte_size": len(raw), "captured_at": "2026-11-15T12:00:00Z"}, {}, raw))
    result = readiness.inspect_job(job, object())
    assert result["records"] == result["physical_rows"] == 1
    assert result["reference_date"] == "2026-11-06"
    assert result["publication_approved"] is False
    assert result["original_and_capture_provenance_verified"] is True
    from white_list_archive.publishing.publication_handoff import records_digest
    from white_list_archive.publishing.public_contract import public_record
    from white_list_archive.publishing.public_national_registry import _parse_source
    original = tmp_path / "source.html"
    original.write_bytes(raw)
    # The verified input uses the exact capture hash, not the legacy
    # configuration hash. Check the same source identity as the producer.
    pinned_config = readiness.transform._parse_config(job)
    pinned_config["reference_date"] = result["reference_date"]
    expected_records = [public_record(row) for row in _parse_source(
        original, pinned_config).records]
    assert result["public_records_sha256"] == records_digest(expected_records)
    assert result["blank_names"] == sum(not row["name"] for row in expected_records)
    assert result["blank_activities"] == sum(not row["requested_activities"] for row in expected_records)
    safe = readiness.public_summary({"kind": "archived-release-readiness", "results": [
        {"authority_key": "taranto", "status": "review_metadata_ready", "sources": [result]}]})
    published = safe["results"][0]["sources"][0]
    assert published["public_records_sha256"] == result["public_records_sha256"]
    assert published["blank_names"] == result["blank_names"]
    assert published["blank_activities"] == result["blank_activities"]
    assert published["publication_approved"] is False


def test_biella_delta_is_multiset_observational_and_redacted():
    def row(name, raw, status="listed", **extra):
        return {"name": name, "identifier_field_raw": raw, "source_status": status, **extra}
    old = [row("SYNTHETIC A", "ABCDEF00A00A000A"), row("SYNTHETIC A", "ABCDEF00A00A000A"),
           row("SYNTHETIC B", "00000000000"), row("SYNTHETIC D", "11111111111")]
    new = [row("SYNTHETIC A", "ABCDEF00A00A000A", "renewal_update_in_progress"),
           row("SYNTHETIC B", "00000000000", reference_date="2026-11-25"),
           row("SYNTHETIC C", "22222222222", outcome_raw="ABCDEF00A00A000A")]
    report = readiness.biella_observation_delta(old, new)
    assert report["shared_text_keys"] == 2
    assert report["old_only_text_keys"] == report["new_only_text_keys"] == 1
    assert report["shared_keys_changed_multiplicity"] == report["shared_keys_changed_status"] == 1
    assert report["shared_keys_changed_values"] == 1
    assert report["old_unmatched_observations"] == 3
    assert report["new_unmatched_observations"] == 2
    assert report["old_identifier_shape_rows"] == 2 and report["new_identifier_shape_rows"] == 1
    assert report["new_other_field_shape_rows"] == 1
    assert "SYNTHETIC" not in json.dumps(report)
    assert "ABCDEF00A00A000A" not in json.dumps(report)


def test_biella_delta_summary_cannot_emit_raw_values():
    safe = readiness.public_summary({"kind": "archived-release-readiness", "results": [
        {"authority_key": "biella", "status": "review_metadata_ready", "sources": [{
            "source_key": "biella-listed", "biella_documentary_delta": {
                "status": "documentary_comparison_ready", "new_observations": 133,
                "old_observations": "PRIVATE", "unexpected": "PRIVATE"}}]}]})
    assert safe["results"][0]["sources"][0]["biella_documentary_delta"] == {
        "status": "documentary_comparison_ready", "new_observations": 133}
    assert "PRIVATE" not in json.dumps(safe)
    assert safe["approvals"] == safe["publications"] == 0


def test_biella_pinned_comparison_rejects_other_original_without_store_access():
    assert readiness._biella_pinned_delta(object(), {"config": {}}, {}, [], "2026-11-25") == {
        "status": "outside_frozen_pair"}


@pytest.mark.parametrize("digest", [
    "60fa8903200505d0621f17685fb9520ed129cdf71cdd8bb582e132743fad23ca",
    "3291b2d7614d961ec2c9ed16fb211ce11132f9ec09659b20c7f85508d802413e",
    "a16b3558ea56d4770efaea46973036a4da1fa8dbc53f33a664aec07c8a46e379",
])
def test_biella_same_date_review_pins_reach_old_original_gate(digest):
    from white_list_archive.publishing import biella_review
    class Store:
        def __init__(self):
            self.calls = []
        def read_digest_verified(self, sha):
            self.calls.append(sha)
            raise ValueError("synthetic unavailable original")
    store = Store()
    cfg = {"sha256": biella_review.SOURCE_SHA256, "reference_date": biella_review.REFERENCE_DATE}
    manifest = {"sha256": digest, "byte_size": 204481}
    result = readiness._biella_pinned_delta(store, {"config": cfg}, manifest, [], "2026-11-25")
    assert result == {"status": "comparison_requires_review"}
    assert store.calls == [biella_review.SOURCE_SHA256]
    for changed, updated in [
        ({**manifest, "sha256": "0" * 64}, "2026-11-25"),
        ({**manifest, "byte_size": 204482}, "2026-11-25"),
        (manifest, "2026-11-26"),
    ]:
        assert readiness._biella_pinned_delta(object(), {"config": cfg}, changed, [], updated) == {
            "status": "outside_frozen_pair"}


def test_biella_delta_distinguishes_nested_locator_and_substantive_changes():
    old = {"name": "SYNTHETIC", "identifier_field_raw": "", "source_status": "listed",
           "source_fields": {"physical_locators": ["row:1"], "notes": ["unchanged"]}}
    new = {**old, "source_fields": {**old["source_fields"], "physical_locators": ["row:2"]}}
    report = readiness.biella_observation_delta([old], [new])
    assert report["shared_keys_changed_values"] == 1
    assert report["shared_keys_locator_only_changes"] == 1
    assert report["shared_keys_changed_substantive_values"] == 0
    new["source_fields"]["notes"] = ["changed"]
    report = readiness.biella_observation_delta([old], [new])
    assert report["shared_keys_locator_only_changes"] == 0
    assert report["shared_keys_changed_substantive_values"] == 1


def test_biella_cf_delta_detects_equal_shape_counts_but_changed_values_and_placement():
    first, second = "ABCDEF00A00A000A", "GHIJKL00A00A000B"
    old = {"name": "SYNTHETIC", "identifier_field_raw": "", "source_status": "listed",
           "source_fields": {"notes": [first]}}
    new = {**old, "source_fields": {"notes": [second]}}
    report = readiness.biella_observation_delta([old], [new])
    assert report["old_other_field_shape_rows"] == report["new_other_field_shape_rows"] == 1
    assert report["old_unmatched_cf_value_occurrences"] == report["new_unmatched_cf_value_occurrences"] == 1
    assert report["old_unmatched_cf_placement_occurrences"] == report["new_unmatched_cf_placement_occurrences"] == 1
    moved = {**old, "source_fields": {"registered_office_variants": [first]}}
    report = readiness.biella_observation_delta([old], [moved])
    assert report["old_unmatched_cf_value_occurrences"] == report["new_unmatched_cf_value_occurrences"] == 0
    assert report["old_unmatched_cf_placement_occurrences"] == report["new_unmatched_cf_placement_occurrences"] == 1
    safe = readiness.public_summary({"kind": "archived-release-readiness", "results": [
        {"authority_key": "biella", "status": "review_metadata_ready", "sources": [
            {"source_key": "biella-listed", "biella_documentary_delta": {
                "status": "documentary_comparison_ready", **report, "raw_token": first}}]}]})
    delta = safe["results"][0]["sources"][0]["biella_documentary_delta"]
    assert delta["new_unmatched_cf_placement_occurrences"] == 1
    assert all(token not in json.dumps(safe) for token in (first, second, "SYNTHETIC", "raw_token"))
    assert safe["approvals"] == safe["publications"] == 0
