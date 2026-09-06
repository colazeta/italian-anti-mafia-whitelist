from __future__ import annotations

import argparse
import importlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import psycopg
except ImportError as exc:  # pragma: no cover
    psycopg = None
    _IMPORT_ERROR = exc
else:
    _IMPORT_ERROR = None

from white_list_archive.parsers.registry import (
    DEFAULT_BINDINGS,
    DEFAULT_FAMILIES,
    DEFAULT_SEMANTIC_PROFILES,
    select_parser,
    semantic_profile_for_family,
)
from white_list_archive.semantic.canonicalise import canonicalise_series

MAPPING_VERSION = "prefecture-combined-whitelist-v1"

FIELD_MAPPINGS: dict[str, list[dict[str, Any]]] = {
    "ragione_sociale": [
        {"canonical_path": "entity_name.name", "rule": "preserve raw business name; normalisation remains supplementary", "confidence": 1.0, "loss": False}
    ],
    "sede_legale": [
        {"canonical_path": "establishment.address", "rule": "project source registered-office string as establishment address observation", "confidence": 1.0, "loss": False}
    ],
    "sede_secondaria": [
        {"canonical_path": "establishment.address", "rule": "project source secondary-office string as establishment address observation", "confidence": 1.0, "loss": False}
    ],
    "codice_fiscale_partita_iva": [
        {"canonical_path": "entity_identifier.value", "rule": "split composite identifier field into preserved source identifier observations", "confidence": 1.0, "loss": True},
        {"canonical_path": "entity_identifier.scheme", "rule": "annotate possible identifier scheme from syntax/source hints without forcing identity", "confidence": 0.9, "loss": True},
    ],
    "attivita_richiesta_iscrizione": [
        {"canonical_path": "procedure.sector_concept", "rule": "map requested activity wording to the applicable versioned White List sector concept", "confidence": 1.0, "loss": True}
    ],
    "data_presentazione_istanza": [
        {"canonical_path": "procedure.application_date", "rule": "parse each source application-date token while preserving parenthesized-source flag", "confidence": 1.0, "loss": False}
    ],
    "esito": [
        {"canonical_path": "relationship_state.administrative_disposition", "rule": "interpret explicit source Esito wording through versioned semantic projector", "confidence": 0.95, "loss": True},
        {"canonical_path": "relationship_state.legal_effect_status", "rule": "project only legal-effect states supported by explicit source wording; otherwise unknown", "confidence": 0.9, "loss": True},
        {"canonical_path": "relationship_state.nominal_valid_from", "rule": "extract observed listing date from explicit Esito wording", "confidence": 1.0, "loss": True},
        {"canonical_path": "relationship_state.nominal_valid_until", "rule": "extract nominal expiry date from explicit Esito wording", "confidence": 1.0, "loss": True},
        {"canonical_path": "procedure.status", "rule": "project procedure status from explicit Esito wording and renewal/update markers", "confidence": 0.95, "loss": True},
        {"canonical_path": "procedure.outcome", "rule": "project approved/rejected/cancelled only when supported by explicit source wording", "confidence": 0.95, "loss": True},
        {"canonical_path": "procedure.decision_date", "rule": "use explicitly observed insertion/decision date only for eligible completed procedures", "confidence": 0.95, "loss": True},
    ],
}


def _series_context(cur, series_code: str) -> dict[str, Any]:
    cur.execute(
        """
        SELECT s.series_id, s.series_code,
               array_agg(DISTINCT sv.structural_fingerprint ORDER BY sv.structural_fingerprint)
        FROM source.source_series s
        JOIN source.source_schema ss ON ss.series_id=s.series_id
        JOIN source.source_schema_version sv ON sv.source_schema_id=ss.source_schema_id
        WHERE s.series_code=%s
        GROUP BY s.series_id,s.series_code
        """,
        (series_code,),
    )
    row = cur.fetchone()
    if not row:
        raise LookupError(f"No schema-version context exists for source series {series_code!r}")
    return {"series_id": row[0], "series_code": row[1], "fingerprints": list(row[2])}


def _select_family(series_code: str, fingerprints: list[str], families_path, bindings_path):
    selections = []
    errors = []
    for fingerprint in fingerprints:
        try:
            selections.append(
                select_parser(
                    series_code,
                    fingerprint,
                    families_path=families_path,
                    bindings_path=bindings_path,
                )
            )
        except LookupError as exc:
            errors.append(str(exc))
    if not selections:
        raise LookupError("; ".join(errors) or f"No parser selection for {series_code!r}")
    family_codes = {selection.family.code for selection in selections}
    if len(family_codes) != 1:
        raise LookupError(
            f"Source series {series_code!r} currently spans multiple validated parser families: "
            f"{sorted(family_codes)}. Run per schema family or add an explicit migration/binding policy."
        )
    return selections[0]


def ensure_field_mappings(
    conn,
    series_id,
    record_contract_code: str,
    field_locator_prefix: str,
) -> dict[str, int]:
    if record_contract_code != "prefecture-combined-whitelist-v1":
        raise LookupError(
            f"No field-mapping profile implemented for record contract {record_contract_code!r}"
        )
    inserted = 0
    existing = 0
    with conn.cursor() as cur:
        cur.execute("SELECT canonical_path,canonical_field_id FROM mapping.canonical_field")
        canonical = {row[0]: row[1] for row in cur.fetchall()}
        missing_paths = sorted(
            {
                mapping["canonical_path"]
                for mappings in FIELD_MAPPINGS.values()
                for mapping in mappings
                if mapping["canonical_path"] not in canonical
            }
        )
        if missing_paths:
            raise LookupError(f"Canonical field registry is missing: {missing_paths}")

        cur.execute(
            """
            SELECT fd.field_definition_id,fd.normalised_source_label
            FROM source.source_field_definition fd
            JOIN source.source_schema_version sv ON sv.schema_version_id=fd.schema_version_id
            JOIN source.source_schema ss ON ss.source_schema_id=sv.source_schema_id
            WHERE ss.series_id=%s AND fd.structural_locator LIKE %s
            """,
            (series_id, field_locator_prefix + "%"),
        )
        definitions = cur.fetchall()
        observed_labels = {row[1] for row in definitions}
        required = set(FIELD_MAPPINGS)
        missing = required - observed_labels
        if missing:
            raise ValueError(
                f"Parser-family field namespace {field_locator_prefix!r} violates semantic record contract "
                f"{record_contract_code!r}; missing definitions {sorted(missing)}"
            )

        for field_definition_id, source_label in definitions:
            for mapping in FIELD_MAPPINGS.get(source_label, []):
                canonical_field_id = canonical[mapping["canonical_path"]]
                cur.execute(
                    """
                    SELECT field_mapping_id
                    FROM mapping.field_mapping
                    WHERE field_definition_id=%s AND canonical_field_id=%s
                      AND mapping_version=%s AND effective_to IS NULL
                    """,
                    (field_definition_id, canonical_field_id, MAPPING_VERSION),
                )
                if cur.fetchone():
                    existing += 1
                    continue
                cur.execute(
                    """
                    INSERT INTO mapping.field_mapping(
                        field_definition_id,canonical_field_id,mapping_rule,mapping_version,
                        confidence,information_loss_flag,effective_from,effective_to
                    ) VALUES (%s,%s,%s,%s,%s,%s,%s,NULL)
                    """,
                    (
                        field_definition_id,
                        canonical_field_id,
                        mapping["rule"],
                        MAPPING_VERSION,
                        mapping["confidence"],
                        mapping["loss"],
                        datetime.now(timezone.utc).replace(microsecond=0),
                    ),
                )
                inserted += 1
    return {"inserted": inserted, "existing": existing}


def run_pipeline(
    conn,
    series_code: str,
    *,
    families_path: Path = DEFAULT_FAMILIES,
    bindings_path: Path = DEFAULT_BINDINGS,
    semantic_profiles_path: Path = DEFAULT_SEMANTIC_PROFILES,
) -> dict[str, Any]:
    with conn.cursor() as cur:
        context = _series_context(cur, series_code)
    selection = _select_family(series_code, context["fingerprints"], families_path, bindings_path)
    profile = semantic_profile_for_family(selection.family, profiles_path=semantic_profiles_path)

    mappings = ensure_field_mappings(
        conn,
        context["series_id"],
        selection.family.record_contract_code,
        selection.family.field_locator_prefix,
    )

    module = importlib.import_module(profile.projector_module)
    project_series = getattr(module, "project_series", None)
    if project_series is None:
        raise AttributeError(f"Semantic projector {profile.projector_module!r} has no project_series()")
    projection = project_series(conn, series_code)
    canonicalisation = canonicalise_series(conn, series_code)

    return {
        "series_code": series_code,
        "schema_fingerprints": context["fingerprints"],
        "parser_selection": {
            "family_code": selection.family.code,
            "implementation_module": selection.family.implementation_module,
            "parser_version": selection.family.parser_version,
            "field_locator_prefix": selection.family.field_locator_prefix,
            "selection_basis": selection.selection_basis,
        },
        "record_contract_code": selection.family.record_contract_code,
        "semantic_profile": {
            "code": profile.code,
            "projector_module": profile.projector_module,
            "projector_version": profile.projector_version,
        },
        "field_mappings": mappings,
        "semantic_projection": projection,
        "canonicalisation": canonicalisation,
    }


def run_from_dsn(
    dsn: str,
    series_code: str,
    *,
    families_path: Path = DEFAULT_FAMILIES,
    bindings_path: Path = DEFAULT_BINDINGS,
    semantic_profiles_path: Path = DEFAULT_SEMANTIC_PROFILES,
) -> dict[str, Any]:
    if psycopg is None:
        raise RuntimeError("psycopg is required; install the 'database' extra") from _IMPORT_ERROR
    with psycopg.connect(dsn) as conn:
        result = run_pipeline(
            conn,
            series_code,
            families_path=families_path,
            bindings_path=bindings_path,
            semantic_profiles_path=semantic_profiles_path,
        )
        conn.commit()
        return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run semantic projection and guarded canonicalisation for a parsed source series."
    )
    parser.add_argument("--dsn", required=True)
    parser.add_argument("--series-code", required=True)
    parser.add_argument("--parser-families", type=Path, default=DEFAULT_FAMILIES)
    parser.add_argument("--parser-bindings", type=Path, default=DEFAULT_BINDINGS)
    parser.add_argument("--semantic-profiles", type=Path, default=DEFAULT_SEMANTIC_PROFILES)
    args = parser.parse_args()
    result = run_from_dsn(
        args.dsn,
        args.series_code,
        families_path=args.parser_families,
        bindings_path=args.parser_bindings,
        semantic_profiles_path=args.semantic_profiles,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
