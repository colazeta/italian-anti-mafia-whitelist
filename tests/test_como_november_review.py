import hashlib
import json

import pytest

from white_list_archive.publishing import como_review as review
from test_como_parser_semantics import _cfg, _write
from white_list_archive.parsers import como_html as family
from white_list_archive.publishing.public_national_registry import _parse_source, _semantic_digest


def fixture(tmp_path, monkeypatch):
    rows = [[family._APPLICANT_TITLE, '', '', '', '', '', '', ''],
            ['NUMERO AZIENDE IN FASE ISCRIZIONE:', '0', '', '', '', '', '', ''],
            list(family._APPLICANT_HEADER),
            ['SYNTHETIC COMPANY', 'COMO', 'RAW-FIXTURE', '', '', 'Sez. I', '', 'nov-26']]
    path = _write(tmp_path, 'source.html', rows)
    path.write_text(path.read_text() + '<p>Ultimo aggiornamento 10 novembre 2026</p>')
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    cfg = {**_cfg('como-applicants', 'applicant'), 'parser': 'como_html_applicants',
           'sha256': sha, 'reference_date': review.REFERENCE_DATE}
    batch = _parse_source(path, cfg)
    monkeypatch.setattr(review, 'PINS', {'como-applicants': {'sha256': sha, 'records': 1,
        'statuses': {'pending': 1}, 'semantic_sha256': _semantic_digest(batch.records)}})
    return path, cfg


def test_exact_source_review_preserves_raw_identifier_and_month_only_dates(tmp_path, monkeypatch):
    path, cfg = fixture(tmp_path, monkeypatch)
    result = review.inspect(path, cfg, checked_at='2026-11-15T12:00:00Z')
    assert result['records'] == result['physical_rows'] == 1
    assert result['counts']['declared_count'] == 0
    assert result['counts']['declared_count_delta'] == 1
    assert result['counts']['raw_identifier_only'] == 1
    assert len(result['public_records_sha256']) == 64
    assert result['approval_granted'] is False and result['publications'] == 0
    assert 'SYNTHETIC COMPANY' not in json.dumps(result)
    with pytest.raises(ValueError):
        review.inspect(path, {**cfg, 'parser': 'other'}, checked_at='2026-11-15T12:00:00Z')
    path.write_text(path.read_text() + 'changed bytes')
    with pytest.raises(ValueError, match='archived source pin'):
        review.inspect(path, cfg, checked_at='2026-11-15T12:00:00Z')


def test_independent_source_census_rejects_what_the_legacy_parser_silently_skips(tmp_path, monkeypatch):
    path, cfg = fixture(tmp_path, monkeypatch)
    path.write_text(path.read_text().replace('</table>', '<tr><td>unclassified</td><td>details</td></tr></table>'))
    # Even if this exact new original had been preserved, unchanged parser
    # semantics are insufficient: every physical row still must be classified.
    review.PINS['como-applicants']['sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
    with pytest.raises(ValueError, match='Unclassified'):
        review.inspect(path, cfg, checked_at='2026-11-15T12:00:00Z')


def test_exact_authority_caption_is_metadata_only_without_other_cell_values(tmp_path, monkeypatch):
    path, cfg = fixture(tmp_path, monkeypatch)
    path.write_text(path.read_text().replace('<table>', '<table><tr><td>Prefettura di Como</td><td></td></tr>'))
    assert review.como_complete_physical_rows(path, 'applicant') == 1
    path.write_text(path.read_text().replace('<td>Prefettura di Como</td><td>', '<td>Prefettura di Como</td><td>UNREVIEWED VALUE'))
    with pytest.raises(ValueError, match='Unclassified'):
        review.como_complete_physical_rows(path, 'applicant')


def test_source_review_failure_never_prints_original_values_or_exception_messages(monkeypatch, capsys):
    def fail(*_):
        raise ValueError('PRIVATE SOURCE VALUES')
    monkeypatch.setattr(review, '_download', fail)
    assert review.main() == 1
    text = capsys.readouterr().out
    assert 'PRIVATE SOURCE VALUES' not in text
    assert json.loads(text)['publications'] == 0


def test_source_pin_failure_has_closed_reason_and_safe_original_metadata(monkeypatch, capsys):
    raw = b'PRIVATE SOURCE VALUES'
    monkeypatch.setattr(review, '_download', lambda url, path: path.write_bytes(raw))
    assert review.main() == 1
    result = json.loads(capsys.readouterr().out)
    for source in result['sources']:
        assert source['failure_code'] == 'original_pin_mismatch'
        assert source['downloaded_sha256'] == hashlib.sha256(raw).hexdigest()
        assert source['downloaded_bytes'] == len(raw)
    assert raw.decode() not in json.dumps(result)
