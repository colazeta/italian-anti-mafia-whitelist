from white_list_archive.storage.legacy_capture_recovery import legacy_capture_id
from white_list_archive.storage.recovery_migration import apply_capture_migrations


def legacy_manifest():
    return {
        "captured_at": "2026-09-06T18:25:35+00:00",
        "sha256": "a" * 64,
        "resource_url": "https://prefettura.example/source.pdf",
        "final_url": "https://prefettura.example/source.pdf",
        "reference_date": "2026-06-28",
    }


def test_legacy_capture_id_uses_historical_provenance_not_processing_time():
    first = legacy_capture_id(source_key="cosenza-combined", manifest=legacy_manifest())
    second = legacy_capture_id(source_key="cosenza-combined", manifest=legacy_manifest())
    assert first == second


def test_capture_migration_replaces_known_version_one_for_one():
    capture = {
        "source_key": "cosenza-combined",
        "capture_id": "11111111-1111-4111-8111-111111111111",
        "sha256": "a" * 64,
        "byte_size": 10,
    }
    expectations = {
        "known_versions": [{
            "authority_key": "cosenza",
            "source_key": "cosenza-combined",
            "evidence_version_key": "legacy-manifest:data/captures/cosenza/example.json",
            "sha256": "a" * 64,
            "byte_size": 10,
        }],
        "captures": [],
    }
    migrated, refs = apply_capture_migrations(
        expectations,
        [{
            "authority_key": "cosenza",
            "evidence_version_key": "legacy-manifest:data/captures/cosenza/example.json",
            "sha256": "a" * 64,
            "capture": capture,
            "catalogue": {"catalogue_key": "captures/v1/example.json"},
            "operator_evidence_refs": ["data/captures/cosenza/example.json"],
        }],
        source_authorities={"cosenza-combined": "cosenza"},
    )
    assert len(migrated["known_versions"]) == 0
    assert len(migrated["captures"]) == 1
    assert len(expectations["known_versions"]) + len(expectations["captures"]) == 1
    assert len(migrated["known_versions"]) + len(migrated["captures"]) == 1
    assert refs[(capture["source_key"], capture["capture_id"])] == [
        "data/captures/cosenza/example.json"
    ]
