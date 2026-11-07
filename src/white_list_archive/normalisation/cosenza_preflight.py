"""Read-only readiness assessment of explicitly pinned historical Cosenza inputs.

Produces aggregate diagnostics only. It cannot approve an edition, persist rows,
select semantic inputs, change privileges, or publish a release.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from uuid import UUID

from white_list_archive.acquisition.auto_transform import private_connection, read_snapshot_verified
from white_list_archive.persistence.legacy_cosenza import SPECS, classification_for
from white_list_archive.parsers import cosenza_combined_v2 as rich
from white_list_archive.storage.capture_catalogue import CaptureCatalogue
from white_list_archive.storage.catalogue_recovery import load_catalogued_capture
from white_list_archive.storage.evidence import EvidenceStore, StoreConfig, client_for


def validate_pins(capture_id: str, parse_run_id: str, revision: str) -> tuple:
    """Reject unknown captures and non-exact execution/run identities early."""
    capture_id, parse_run_id = str(UUID(capture_id)), str(UUID(parse_run_id))
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ValueError("An exact code revision is required")
    spec = next((item for item in SPECS if item[1] == capture_id), None)
    if spec is None:
        raise ValueError("Capture is outside the reviewed historical Cosenza set")
    return spec


def verify_relational_input(conn, *, capture_id: str, parse_run_id: str,
                            sha256: str) -> list:
    """Require a succeeded scalar run and exact capture/ContentObject association.

    This helper performs SELECT only; its caller owns the transaction boundary.
    Edition links are evidence to report, never an approval decision.
    """
    with conn.cursor() as cur:
        cur.execute("""SELECT co.sha256 FROM source.capture_parse_run cpr
            JOIN source.source_capture sc ON sc.capture_id=cpr.capture_id
            JOIN source.content_object co ON co.content_object_id=sc.content_object_id
            JOIN source.parse_run pr ON pr.parse_run_id=cpr.parse_run_id
              AND pr.content_object_id=sc.content_object_id AND pr.status_code='succeeded'
            JOIN source.parse_run_input i ON i.parse_run_id=cpr.parse_run_id
              AND i.input_label=cpr.input_label AND i.content_object_id=sc.content_object_id
            WHERE cpr.capture_id=%s AND cpr.parse_run_id=%s AND cpr.input_label='primary'
              AND (SELECT count(*) FROM source.parse_run_input all_inputs
                   WHERE all_inputs.parse_run_id=pr.parse_run_id)=1""", (capture_id, parse_run_id))
        inputs = cur.fetchall()
        if len(inputs) != 1 or inputs[0][0] != sha256:
            raise ValueError("Pinned run lacks a succeeded scalar matching capture input")
        cur.execute("""SELECT e.edition_id, e.edition_identity_status_code,
                   ce.attribution_status_code FROM source.capture_edition ce
            JOIN source.source_edition e ON e.edition_id=ce.edition_id
            WHERE ce.capture_id=%s""", (capture_id,))
        return cur.fetchall()


def assess(conn, store, root: Path, *, capture_id: str, parse_run_id: str,
           revision: str) -> dict:
    filename, _, expected = validate_pins(capture_id, parse_run_id, revision)
    historical = json.loads((root / "data/captures/cosenza" / filename).read_text())
    manifest, _ = load_catalogued_capture(CaptureCatalogue(store),
        source_key="cosenza-combined", capture_id=capture_id)
    classification_for(manifest, historical, filename=filename)
    original = store.read_verified(manifest)
    if len(original) != historical["byte_size"] or hashlib.sha256(original).hexdigest() != historical["sha256"]:
        raise ValueError("Original differs from reviewed historical bytes")
    with conn.cursor() as cur:
        # This must precede any relational query in the production transaction.
        cur.execute("SET TRANSACTION READ ONLY")
    editions = verify_relational_input(conn, capture_id=capture_id,
        parse_run_id=parse_run_id, sha256=manifest["sha256"])
    snapshot, _ = read_snapshot_verified(conn, parse_run_id)
    if len(snapshot) != expected:
        raise ValueError("Pinned snapshot differs from historical row denominator")
    with tempfile.TemporaryDirectory(prefix="private-cosenza-rich-") as directory:
        path = Path(directory) / "original.pdf"
        path.write_bytes(original)
        records = rich.parse_pdf(path)
    if len(records) != expected:
        raise ValueError("Rich parser differs from reviewed historical row denominator")
    if len({row["row_ordinal"] for row in records}) != len(records):
        raise ValueError("Rich parser emitted duplicate row ordinals")
    return {"kind": "cosenza-rich-read-only-preflight", "capture_id": capture_id,
        "parse_run_id": parse_run_id, "code_revision": revision,
        "original_sha256": manifest["sha256"], "original_verified": True,
        "snapshot_verified": True, "expected_records": expected,
        "snapshot_records": len(snapshot), "rich_records": len(records),
        "rich_parser": rich.PARSER_NAME, "rich_parser_version": rich.PARSER_VERSION,
        "rich_configuration_sha256": rich.PARSER_CONFIGURATION_HASH,
        "edition_links": [{"edition_id": str(e), "identity_status": status,
                           "attribution_status": attribution} for e, status, attribution in editions],
        "quality_approval_assessed": False, "edition_approval_assessed": False, "semantic_selection_performed": False,
        "writes": 0, "publications": 0}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture-id", required=True)
    parser.add_argument("--parse-run-id", required=True)
    parser.add_argument("--code-revision", required=True)
    args = parser.parse_args(argv)
    validate_pins(args.capture_id, args.parse_run_id, args.code_revision)
    config = StoreConfig.from_env()
    store = EvidenceStore(client_for(config), config)
    with private_connection(os.environ["EVIDENCE_DATABASE_URL"]) as conn:
        result = assess(conn, store, Path(__file__).resolve().parents[3],
            capture_id=args.capture_id, parse_run_id=args.parse_run_id,
            revision=args.code_revision)
        conn.rollback()
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
