from white_list_archive.publishing.public_national_registry import _semantic_digest


def _record(**changes):
    record = {
        "name": "Example S.r.l.",
        "source_status": "listed",
        "capture_sha256": "raw-a",
        "parser_name": "parser-a",
        "parser_version": "1",
    }
    record.update(changes)
    return record


def test_semantic_digest_ignores_only_capture_and_runtime_parser_provenance():
    baseline = _semantic_digest([_record()])
    assert baseline == _semantic_digest([_record(capture_sha256="raw-b", parser_name="parser-b", parser_version="2")])
    assert baseline != _semantic_digest([_record(name="Different S.r.l.")])
    assert baseline != _semantic_digest([_record(source_status="pending")])


def test_semantic_digest_is_order_sensitive_for_source_rows():
    assert _semantic_digest([_record(name="A"), _record(name="B")]) != _semantic_digest([_record(name="B"), _record(name="A")])
