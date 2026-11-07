"""Consistent private database KPI checkpoints; no rows or credentials exported."""
from __future__ import annotations

import argparse
import json
import os
import re

from white_list_archive.acquisition.auto_transform import private_connection, persist_operational_report

# Fixed names only: SQL identifiers are never supplied by a caller.
TABLES = {
    "captures": "source.source_capture",
    "content_objects": "source.content_object",
    "snapshots": "source.parse_snapshot",
    "capture_interpretation_links": "source.capture_parse_run",
    "parsed_records": "source.parsed_record",
    "administrative_editions": "source.source_edition",
    "semantic_observations": "semantic.entity_observation",
    "canonical_entities": "core.legal_entity",
}


def collect_checkpoint(conn, *, code_revision: str) -> dict:
    if not re.fullmatch(r"[0-9a-f]{40}", code_revision):
        raise ValueError("Exact code revision required")
    metrics = {}
    with conn.cursor() as cur:
        # A transaction-wide snapshot prevents concurrent ingestion from making
        # the denominators disagree. Caller must provide a fresh connection.
        cur.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
        cur.execute("SELECT transaction_timestamp()")
        checked_at = cur.fetchone()[0].isoformat()
        for key, table in TABLES.items():
            schema, name = table.split(".")
            cur.execute("""SELECT has_schema_privilege(n.oid,'USAGE')
                                  AND has_table_privilege(c.oid,'SELECT')
                           FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
                           WHERE n.nspname=%s AND c.relname=%s AND c.relkind='r'""",
                        (schema, name))
            privilege = cur.fetchone()
            if not privilege or not privilege[0]:
                metrics[key] = {"value": None, "status": "not_verified",
                                "reason": "reader_unavailable", "origin": table}
                continue
            cur.execute(f"SELECT count(*) FROM {table}")
            metrics[key] = {"value": int(cur.fetchone()[0]), "status": "verified",
                            "unit": "database_rows", "origin": table}
        if metrics["content_objects"]["status"] == "verified":
            cur.execute("SELECT count(*) FROM source.content_object WHERE storage_status_code='durable'")
            metrics["durable_content_objects"] = {
                "numerator": int(cur.fetchone()[0]),
                "denominator": metrics["content_objects"]["value"],
                "status": "verified", "origin": "source.content_object.storage_status_code",
                "scope": "database registrations; not a new provider byte readback",
            }
        if metrics["snapshots"]["status"] == "verified":
            cur.execute("""SELECT coalesce(sum(record_count),0),
                                  count(*) FILTER (WHERE record_count<>jsonb_array_length(records_json))
                           FROM source.parse_snapshot""")
            occurrences, mismatches = cur.fetchone()
            metrics["snapshot_record_occurrences"] = {
                "value": int(occurrences), "unit": "records_across_interpretation_revisions",
                "status": "verified", "origin": "source.parse_snapshot.record_count",
                "distinct_business_count": False,
            }
            metrics["snapshot_count_mismatches"] = {
                "numerator": int(mismatches), "denominator": metrics["snapshots"]["value"],
                "status": "verified", "origin": "stored record_count versus JSON array length",
                "scope": "structural count check; not a canonical SHA-256 rehash",
            }
    return {"kind": "private-production-checkpoint", "schema_version": 1,
            "code_revision": code_revision, "checked_at": checked_at,
            "metrics": metrics, "publications": 0,
            "independent_backup_verified": None, "release_approval_verified": None}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--code-revision", required=True)
    args = parser.parse_args(argv)
    from white_list_archive.storage.evidence import EvidenceStore, StoreConfig, client_for
    config = StoreConfig.from_env()
    store = EvidenceStore(client_for(config), config)
    try:
        with private_connection(os.environ["EVIDENCE_DATABASE_URL"]) as conn:
            report = collect_checkpoint(conn, code_revision=args.code_revision)
        persist_operational_report(store, report)
    except Exception:
        # Database/provider errors can contain private coordinates or queries.
        print(json.dumps({"checkpoint_persisted": False, "publications": 0}))
        return 1
    print(json.dumps({"checkpoint_persisted": True,
                      "verified_metrics": sum(m["status"] == "verified" for m in report["metrics"].values()),
                      "unverified_metrics": sum(m["status"] != "verified" for m in report["metrics"].values()),
                      "publications": 0}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
