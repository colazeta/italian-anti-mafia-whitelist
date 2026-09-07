from __future__ import annotations

import argparse
import json
import re
import uuid
from collections import defaultdict
from pathlib import Path
from typing import Any

try:
    import psycopg
except ImportError as exc:  # pragma: no cover
    psycopg = None
    _IMPORT_ERROR = exc
else:
    _IMPORT_ERROR = None

from .explorer_address_validation_patch import (
    REVIEW_FIELDS,
    _fingerprint,
    _load_json,
    _read_csv,
    patch_explorer,
)

ROW_LOCATOR_RE = re.compile(r"^row:(\d+)$")


def source_occurrences(
    dsn: str,
    address_ids: list[str],
    source_evidence: dict[str, Any],
) -> dict[str, list[dict[str, Any]]]:
    """Resolve sampled canonical addresses back to deterministic source rows.

    The inner SELECT performs de-duplication; ordering happens in the outer
    SELECT using projected aliases. This is portable PostgreSQL semantics for
    SELECT DISTINCT and keeps the evidence list deterministic.
    """
    if psycopg is None:
        raise RuntimeError(
            "psycopg is required; install the project with the database extra"
        ) from _IMPORT_ERROR
    if not address_ids:
        return {}

    ids = [uuid.UUID(value) for value in address_ids]
    sql = """
        WITH requested(address_id) AS (
            SELECT unnest(%s::uuid[])
        ), source_rows AS (
            SELECT DISTINCT
                r.address_id::text AS address_id,
                e.legal_entity_id::text AS legal_entity_id,
                COALESCE(en.name, '') AS entity_name,
                eo.observation_date::text AS observation_date,
                pr.record_locator AS record_locator
            FROM requested r
            JOIN core.establishment_address ea
              ON ea.address_id = r.address_id
             AND upper_inf(ea.system_period)
            JOIN core.establishment e
              ON e.establishment_id = ea.establishment_id
             AND upper_inf(e.system_period)
            LEFT JOIN LATERAL (
                SELECT n.name
                FROM core.entity_name n
                WHERE n.legal_entity_id = e.legal_entity_id
                  AND n.name_type_code = 'legal_name'
                  AND upper_inf(n.system_period)
                ORDER BY lower(n.system_period) DESC, n.entity_name_id
                LIMIT 1
            ) en ON true
            JOIN semantic.entity_projection_resolution er
              ON er.legal_entity_id = e.legal_entity_id
             AND er.decision_status_code = 'accepted'
            JOIN semantic.entity_observation eo
              ON eo.entity_observation_id = er.entity_observation_id
            JOIN semantic.establishment_observation eso
              ON eso.entity_observation_id = eo.entity_observation_id
             AND btrim(eso.full_address_raw) = (
                 SELECT btrim(a.full_address)
                 FROM core.address a
                 WHERE a.address_id = r.address_id
             )
            JOIN source.parsed_record pr
              ON pr.parsed_record_id = eo.parsed_record_id
        )
        SELECT
            address_id,
            legal_entity_id,
            entity_name,
            observation_date,
            record_locator
        FROM source_rows
        ORDER BY address_id, observation_date, record_locator, legal_entity_id
    """

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    with psycopg.connect(dsn) as conn, conn.cursor() as cur:
        cur.execute(sql, (ids,))
        for (
            address_id,
            entity_id,
            entity_name,
            observation_date,
            record_locator,
        ) in cur.fetchall():
            item: dict[str, Any] = {
                "legal_entity_id": entity_id,
                "entity_name": entity_name,
                "observation_date": observation_date,
                "record_locator": record_locator,
            }
            match = ROW_LOCATOR_RE.fullmatch(record_locator or "")
            edition = source_evidence.get("editions", {}).get(observation_date, {})
            if match and isinstance(edition, dict):
                ordinal = str(int(match.group(1)))
                page = (edition.get("rows") or {}).get(ordinal, {}).get("page_start")
                pdf_path = edition.get("pdf_path")
                if page and pdf_path:
                    item["row_ordinal"] = int(ordinal)
                    item["page_start"] = int(page)
                    item["source_pdf_href"] = f"{pdf_path}#page={int(page)}"
            grouped[address_id].append(item)
    return dict(grouped)


def build_review_payload(
    *,
    dsn: str,
    sample_path: Path,
    summary_path: Path,
    source_evidence_path: Path,
) -> dict[str, Any]:
    rows = _read_csv(sample_path)
    summary = _load_json(summary_path)
    evidence = _load_json(source_evidence_path)
    sample_ids = [row["address_id"] for row in rows]
    occurrences = source_occurrences(dsn, sample_ids, evidence)

    output_rows: list[dict[str, Any]] = []
    for position, row in enumerate(rows, start=1):
        item: dict[str, Any] = dict(row)
        item["sample_position"] = position
        item["source_occurrences"] = occurrences.get(row["address_id"], [])
        for field in REVIEW_FIELDS:
            item[field] = ""
        output_rows.append(item)

    return {
        "schema_version": 1,
        "sample_fingerprint": _fingerprint(sample_path, summary_path),
        "sample_size": len(output_rows),
        "summary": summary,
        "review_fields": list(REVIEW_FIELDS),
        "rows": output_rows,
        "source_evidence_archive_policy": evidence.get("archive_policy"),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Build source-linked review payload and add the manual address-validation "
            "tab to the retro Dataset Explorer."
        )
    )
    parser.add_argument("--index", type=Path, required=True)
    parser.add_argument("--dsn", required=True)
    parser.add_argument("--sample", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--source-evidence", type=Path, required=True)
    args = parser.parse_args()

    payload = build_review_payload(
        dsn=args.dsn,
        sample_path=args.sample,
        summary_path=args.summary,
        source_evidence_path=args.source_evidence,
    )
    patch_explorer(args.index, payload)
    result = {
        "index": str(args.index),
        "sample_size": payload["sample_size"],
        "sample_fingerprint": payload["sample_fingerprint"],
        "rows_with_source_occurrences": sum(
            bool(row["source_occurrences"]) for row in payload["rows"]
        ),
        "source_occurrence_count": sum(
            len(row["source_occurrences"]) for row in payload["rows"]
        ),
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
