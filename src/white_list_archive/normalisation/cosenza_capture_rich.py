"""Explicit source-only materialisation mode for the existing Cosenza preflight."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path
import tempfile

from white_list_archive.acquisition.auto_transform import private_connection
from white_list_archive.normalisation.cosenza_preflight import assess, validate_pins
from white_list_archive.parsers import cosenza_combined_v2 as parser
from white_list_archive.persistence.capture_rich_cosenza import (
    MissingSourcePrivileges, missing_privileges, persist_capture_records, verify_rich_readback,
)
from white_list_archive.persistence.legacy_cosenza import classification_for
from white_list_archive.storage.capture_catalogue import CaptureCatalogue
from white_list_archive.storage.catalogue_recovery import load_catalogued_capture
from white_list_archive.storage.evidence import EvidenceStore, StoreConfig, client_for


def materialise(*, capture_id, parse_run_id, code_revision):
    """Pin old aggregate snapshot as prerequisite; append a separately versioned rich run."""
    filename, _, expected_count = validate_pins(capture_id, parse_run_id, code_revision)
    root = Path(__file__).resolve().parents[3]
    config = StoreConfig.from_env()
    store = EvidenceStore(client_for(config), config)
    dsn = os.environ['EVIDENCE_DATABASE_URL']
    # Check all source-only privileges before any side effect or expensive parse.
    with private_connection(dsn) as conn:
        missing = missing_privileges(conn)
        if missing:
            raise MissingSourcePrivileges(missing)
        conn.rollback()
    with private_connection(dsn) as conn:
        readiness = assess(conn, store, root, capture_id=capture_id,
            parse_run_id=parse_run_id, revision=code_revision)
        conn.rollback()
    import json
    historical = json.loads((root / 'data/captures/cosenza' / filename).read_text())
    manifest, _ = load_catalogued_capture(CaptureCatalogue(store),
        source_key='cosenza-combined',capture_id=capture_id)
    classification_for(manifest,historical,filename=filename)
    data = store.read_verified(manifest)
    if len(data) != historical['byte_size'] or hashlib.sha256(data).hexdigest() != historical['sha256']:
        raise ValueError('Rich materialisation original differs from the reviewed archived bytes')
    with tempfile.TemporaryDirectory(prefix='private-capture-rich-') as directory:
        path = Path(directory) / 'original.pdf'
        path.write_bytes(data)
        started = datetime.now(timezone.utc)
        records = parser.parse_pdf(path)
        completed = datetime.now(timezone.utc)
    with private_connection(dsn) as conn:
        result = persist_capture_records(conn,capture_id=capture_id,
            source_sha256=manifest['sha256'],records=records,code_revision=code_revision,
            started_at=started,completed_at=completed,expected_count=expected_count)
        conn.commit()
    # A new TLS connection reads committed records, fields, mentions and lineage.
    with private_connection(dsn) as conn:
        verified = verify_rich_readback(conn,capture_id=capture_id,
            parse_run_id=result['parse_run_id'],source_sha256=manifest['sha256'],
            expected_count=expected_count,expected_snapshot_sha256=result['snapshot_sha256'],
            code_revision=code_revision)
        conn.rollback()
    return {**verified, 'capture_id':capture_id,'prerequisite_parse_run_id':parse_run_id,
            'code_revision':code_revision,'parse_run_reused':result['parse_run_reused'],
            'snapshot_reused':result['snapshot_reused'],'preflight_verified':readiness['snapshot_verified'],
            'committed_readback_verified':True,'mode':'persist-source-only',
            'semantic_writes':0,'canonical_writes':0,'edition_approvals':0}
