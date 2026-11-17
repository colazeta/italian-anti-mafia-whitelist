import importlib.util
import json
from pathlib import Path
import pytest
from white_list_archive.publishing.public_snapshot import FILES, pack

spec = importlib.util.spec_from_file_location('restore_protected_candidate',
    Path(__file__).resolve().parents[1]/'scripts/restore_protected_candidate.py')
consumer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(consumer)


def test_protected_restore_checks_every_derivative_and_source_census(tmp_path):
    data, bundle, target, work = (tmp_path/k for k in ('data', 'bundle', 'target', 'work'))
    data.mkdir()
    target.mkdir()
    for name in FILES:
        (data/name).write_bytes(name.encode())
    pack(data, bundle, 'public-data-test')
    changes = {'alpha': {'count': 7}}
    qa = bundle/'source-qa.json'
    qa.write_text(json.dumps({'alpha': {'public_records': 7}}))
    consumer.restore(bundle, changes, target, work)
    assert {p.name: p.read_bytes() for p in target.iterdir()} == {n: n.encode() for n in FILES}
    qa.write_text(json.dumps({'alpha': {'public_records': 6}}))
    with pytest.raises(ValueError, match='census'):
        consumer.restore(bundle, changes, target, work)
    qa.write_text(json.dumps({'alpha': {'public_records': 7}}))
    (bundle/'registry.csv.gz').write_bytes((bundle/'history.json.gz').read_bytes())
    with pytest.raises(ValueError, match='integrity mismatch'):
        consumer.restore(bundle, changes, target, work)
