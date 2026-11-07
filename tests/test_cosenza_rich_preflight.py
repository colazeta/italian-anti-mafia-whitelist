import pytest
from white_list_archive.normalisation.cosenza_preflight import validate_pins
from white_list_archive.persistence.legacy_cosenza import SPECS


def test_only_exact_reviewed_capture_and_revision_are_accepted():
    assert validate_pins(SPECS[0][1], SPECS[1][1], "a" * 40) == SPECS[0]
    with pytest.raises(ValueError):
        validate_pins("00000000-0000-0000-0000-000000000000", SPECS[1][1], "a" * 40)
    with pytest.raises(ValueError):
        validate_pins(SPECS[0][1], "latest", "a" * 40)
    with pytest.raises(ValueError):
        validate_pins(SPECS[0][1], SPECS[1][1], "main")


def test_mismatched_relational_input_stops_before_parsing(monkeypatch, tmp_path):
    import hashlib
    import json
    from white_list_archive.normalisation import cosenza_preflight as module
    body = b'archived bytes'
    historical = {'byte_size': len(body), 'sha256': hashlib.sha256(body).hexdigest()}
    manifest = dict(historical)
    directory = tmp_path / 'data/captures/cosenza'
    directory.mkdir(parents=True)
    (directory / SPECS[0][0]).write_text(json.dumps(historical))
    monkeypatch.setattr(module, 'load_catalogued_capture', lambda *a, **k: (manifest, {}))
    monkeypatch.setattr(module, 'classification_for', lambda *a, **k: {})
    monkeypatch.setattr(module, 'CaptureCatalogue', lambda store: None)
    class Store:
        def read_verified(self, value):
            return body
    class Cursor:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def execute(self, query, params=None):
            assert query.lstrip().startswith(('SET TRANSACTION READ ONLY', 'SELECT'))
        def fetchall(self):
            return [('different hash',)]
    class Connection:
        def cursor(self):
            return Cursor()
    monkeypatch.setattr(module.rich, 'parse_pdf', lambda path: pytest.fail('must stop before parsing'))
    with pytest.raises(ValueError, match='matching capture input'):
        module.assess(Connection(), Store(), tmp_path, capture_id=SPECS[0][1],
                      parse_run_id=SPECS[1][1], revision='a' * 40)
