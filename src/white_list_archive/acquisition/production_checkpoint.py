"""Consistent private database KPI checkpoints; no rows or credentials exported."""
from __future__ import annotations

import argparse
import json
import os
import re

from white_list_archive.acquisition.auto_transform import private_connection, persist_operational_report

# Fixed names only: SQL identifiers are never supplied by a caller.
TABLES = {
    "source_series": "source.source_series",
    "captures": "source.source_capture",
    "content_objects": "source.content_object",
    "parse_runs": "source.parse_run",
    "parse_run_inputs": "source.parse_run_input",
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
                "integrity_status": "failed" if mismatches else "passed",
                "scope": "structural count check; not a canonical SHA-256 rehash",
            }
        if all(metrics[k]["status"] == "verified" for k in ("parse_runs", "snapshots")):
            metrics["parse_run_snapshot_coverage"] = {
                "numerator": metrics["snapshots"]["value"],
                "denominator": metrics["parse_runs"]["value"],
                "status": "verified", "origin": "source.parse_snapshot / source.parse_run",
                "unit": "interpretation_runs", "scope": "persisted snapshots; not edition approval",
            }
        else:
            metrics["parse_run_snapshot_coverage"] = {
                "numerator": None, "denominator": metrics["parse_runs"].get("value"),
                "status": "not_verified", "reason": "reader_unavailable",
                "origin": "source.parse_snapshot / source.parse_run",
            }
        required = ("captures", "capture_interpretation_links", "parse_run_inputs", "snapshots")
        if all(metrics[k]["status"] == "verified" for k in required):
            # The primary parse_run anchor is insufficient for a bundle: match
            # the exact input label before counting a capture as interpreted.
            cur.execute("""SELECT count(*), count(DISTINCT c.series_id)
                           FROM source.source_capture c
                           WHERE EXISTS (
                               SELECT 1 FROM source.capture_parse_run cp
                               JOIN source.parse_run_input i
                                 ON i.parse_run_id=cp.parse_run_id AND i.input_label=cp.input_label
                               JOIN source.parse_snapshot s ON s.parse_run_id=cp.parse_run_id
                               WHERE cp.capture_id=c.capture_id
                                 AND i.content_object_id=c.content_object_id)""")
            interpreted_captures, interpreted_series = cur.fetchone()
            metrics["capture_interpretation_coverage"] = {
                "numerator": int(interpreted_captures), "denominator": metrics["captures"]["value"],
                "status": "verified", "unit": "captures",
                "origin": "source.source_capture / labelled parse input / persisted snapshot",
                "scope": "any persisted interpretation revision; not latest-version or approval coverage",
            }
            metrics["series_interpretation_coverage"] = {
                "numerator": int(interpreted_series), "denominator": metrics["source_series"].get("value"),
                "status": "verified" if metrics["source_series"]["status"] == "verified" else "not_verified",
                "unit": "registered_source_series", "origin": "distinct source.source_capture.series_id",
                "scope": "at least one interpreted capture; not complete historical coverage",
            }
            if metrics["series_interpretation_coverage"]["status"] == "not_verified":
                metrics["series_interpretation_coverage"]["reason"] = "denominator_reader_unavailable"
            cur.execute("""SELECT count(*) FROM source.capture_parse_run cp
                           LEFT JOIN source.source_capture c ON c.capture_id=cp.capture_id
                           LEFT JOIN source.parse_run_input i
                             ON i.parse_run_id=cp.parse_run_id AND i.input_label=cp.input_label
                           WHERE c.content_object_id IS NULL OR i.content_object_id IS NULL
                              OR c.content_object_id IS DISTINCT FROM i.content_object_id""")
            mismatches = int(cur.fetchone()[0])
            metrics["capture_parse_input_mismatches"] = {
                "numerator": mismatches,
                "denominator": metrics["capture_interpretation_links"]["value"],
                "status": "verified", "integrity_status": "failed" if mismatches else "passed",
                "unit": "capture_interpretation_links",
                "origin": "capture ContentObject versus exact labelled parse_run_input ContentObject",
            }
        else:
            for key, denominator in (("capture_interpretation_coverage", "captures"),
                                     ("series_interpretation_coverage", "source_series"),
                                     ("capture_parse_input_mismatches", "capture_interpretation_links")):
                metrics[key] = {"numerator": None, "denominator": metrics[denominator].get("value"),
                                "status": "not_verified", "reason": "reader_unavailable",
                                "origin": "labelled capture/parse/snapshot relational check"}
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
    failed_integrity_checks = sum(m.get("integrity_status") == "failed" for m in report["metrics"].values())
    print(json.dumps({"checkpoint_persisted": True,
                      "verified_metrics": sum(m["status"] == "verified" for m in report["metrics"].values()),
                      "unverified_metrics": sum(m["status"] != "verified" for m in report["metrics"].values()),
                      "failed_integrity_checks": failed_integrity_checks,
                      "publications": 0}, sort_keys=True))
    return int(failed_integrity_checks > 0)


if __name__ == "__main__":
    raise SystemExit(main())
