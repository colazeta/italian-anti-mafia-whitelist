from __future__ import annotations

from datetime import datetime, timezone
import io

import pytest

from white_list_archive.acquisition.archive_first import archive_payload, main as archive_first_main
from white_list_archive.storage.evidence import EvidenceStore, StoreConfig


class MemoryClient:
    def __init__(self):
        self.objects: dict[str, bytes] = {}
        self.puts: list[str] = []

    def put_object(self, *, Bucket, Key, Body, **kwargs):
        self.puts.append(Key)
        self.objects[Key] = bytes(Body)
        return {}

    def get_object(self, *, Bucket, Key):
        return {"Body": io.BytesIO(self.objects[Key])}


def _store(client: MemoryClient) -> EvidenceStore:
    return EvidenceStore(
        client,
        StoreConfig(
            bucket="archive-bucket",
            endpoint="https://evidence.example",
            region="auto",
            policy_evidence="internal-policy-record",
        ),
    )


@pytest.mark.parametrize(
    ("source_key", "capture_id", "error"),
    [
        (
            "INVALID/source",
            "11111111-1111-4111-8111-111111111111",
            "Invalid source_key",
        ),
        (
            "alpha-listed",
            "not-a-canonical-uuid",
            "canonical UUID",
        ),
    ],
)
def test_invalid_capture_identity_fails_before_staging_or_content_write(
    tmp_path, source_key, capture_id, error
):
    client = MemoryClient()
    work_dir = tmp_path / "capture-work"

    with pytest.raises(ValueError, match=error):
        archive_payload(
            data=b"official bytes that must not become an unbound object",
            source_key=source_key,
            resource_url="https://prefettura.example/white-list.pdf",
            reference_date=None,
            content_type="application/pdf",
            store=_store(client),
            work_dir=work_dir,
            captured_at=datetime(2026, 9, 23, 18, 30, tzinfo=timezone.utc),
            capture_id=capture_id,
            http_status=200,
        )

    assert client.puts == []
    assert client.objects == {}
    assert not work_dir.exists()


def test_cli_rejects_unreviewed_source_series_before_network_or_provider_setup(tmp_path):
    series_registry = tmp_path / "source_series_inventory.csv"
    series_registry.write_text(
        "source_series_key,authority_key\nreviewed-listed,alpha\n",
        encoding="utf-8",
    )
    missing_authority_registry = tmp_path / "territorial_authorities.csv"
    work_dir = tmp_path / "capture-work"
    receipt = tmp_path / "public" / "receipt.json"

    # The key is syntactically valid, so this specifically exercises repository review
    # rather than the CaptureCatalogue syntax check covered above. The failure must
    # happen before StoreConfig/provider setup or any network acquisition is attempted.
    with pytest.raises(ValueError, match="not present in the reviewed source-series inventory"):
        archive_first_main(
            [
                "--source-key",
                "typo-but-syntactically-valid-listed",
                "--resource-url",
                "https://prefettura.example/white-list.pdf",
                "--authority-registry",
                str(missing_authority_registry),
                "--series-registry",
                str(series_registry),
                "--work-dir",
                str(work_dir),
                "--public-receipt",
                str(receipt),
            ]
        )

    assert not work_dir.exists()
    assert not receipt.exists()
