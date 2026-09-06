from __future__ import annotations

import argparse
import importlib
import json
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
    semantic_profile_for_family,
)
from white_list_archive.semantic import pipeline as base
from white_list_archive.semantic.canonicalise_v2 import canonicalise_series


def run_pipeline(
    conn,
    series_code: str,
    *,
    families_path: Path = DEFAULT_FAMILIES,
    bindings_path: Path = DEFAULT_BINDINGS,
    semantic_profiles_path: Path = DEFAULT_SEMANTIC_PROFILES,
) -> dict[str, Any]:
    with conn.cursor() as cur:
        context = base._series_context(cur, series_code)
    selection = base._select_family(
        series_code, context["fingerprints"], families_path, bindings_path
    )
    profile = semantic_profile_for_family(
        selection.family, profiles_path=semantic_profiles_path
    )

    mappings = base.ensure_field_mappings(
        conn,
        context["series_id"],
        selection.family.record_contract_code,
        selection.family.field_locator_prefix,
    )

    module = importlib.import_module(profile.projector_module)
    project_series = getattr(module, "project_series", None)
    if project_series is None:
        raise AttributeError(
            f"Semantic projector {profile.projector_module!r} has no project_series()"
        )
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
        raise RuntimeError(
            "psycopg is required; install the 'database' extra"
        ) from _IMPORT_ERROR
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
        description=(
            "Run current semantic projection and guarded canonicalisation for a "
            "parsed source series."
        )
    )
    parser.add_argument("--dsn", required=True)
    parser.add_argument("--series-code", required=True)
    parser.add_argument("--parser-families", type=Path, default=DEFAULT_FAMILIES)
    parser.add_argument("--parser-bindings", type=Path, default=DEFAULT_BINDINGS)
    parser.add_argument(
        "--semantic-profiles", type=Path, default=DEFAULT_SEMANTIC_PROFILES
    )
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
