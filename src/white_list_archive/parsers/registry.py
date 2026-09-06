from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_FAMILIES = ROOT / "data/source_registry/parser_families.csv"
DEFAULT_BINDINGS = ROOT / "data/source_registry/parser_bindings.csv"
DEFAULT_SEMANTIC_PROFILES = ROOT / "data/source_registry/semantic_profiles.csv"


@dataclass(frozen=True)
class ParserFamily:
    code: str
    implementation_module: str
    parser_version: str
    record_contract_code: str
    semantic_profile_code: str
    field_locator_prefix: str
    supported_schema_fingerprints: tuple[str, ...]
    validation_status: str
    description: str


@dataclass(frozen=True)
class ParserSelection:
    family: ParserFamily
    source_series_key: str
    selection_basis: str
    priority: int


@dataclass(frozen=True)
class SemanticProfile:
    code: str
    projector_module: str
    projector_version: str
    record_contract_code: str
    validation_status: str
    description: str


def _rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def load_families(path: Path = DEFAULT_FAMILIES) -> dict[str, ParserFamily]:
    result: dict[str, ParserFamily] = {}
    for row in _rows(path):
        code = row["parser_family_code"]
        fingerprints = tuple(
            item.strip()
            for item in row["supported_schema_fingerprints"].split(";")
            if item.strip()
        )
        prefix = row["field_locator_prefix"].strip()
        if not prefix:
            raise ValueError(f"Parser family {code!r} requires a field_locator_prefix")
        result[code] = ParserFamily(
            code=code,
            implementation_module=row["implementation_module"],
            parser_version=row["parser_version"],
            record_contract_code=row["record_contract_code"],
            semantic_profile_code=row["semantic_profile_code"],
            field_locator_prefix=prefix,
            supported_schema_fingerprints=fingerprints,
            validation_status=row["validation_status"],
            description=row["description"],
        )
    return result


def load_semantic_profiles(
    path: Path = DEFAULT_SEMANTIC_PROFILES,
) -> dict[str, SemanticProfile]:
    result: dict[str, SemanticProfile] = {}
    for row in _rows(path):
        code = row["semantic_profile_code"]
        result[code] = SemanticProfile(
            code=code,
            projector_module=row["projector_module"],
            projector_version=row["projector_version"],
            record_contract_code=row["record_contract_code"],
            validation_status=row["validation_status"],
            description=row["description"],
        )
    return result


def select_parser(
    source_series_key: str,
    schema_fingerprint: str,
    *,
    families_path: Path = DEFAULT_FAMILIES,
    bindings_path: Path = DEFAULT_BINDINGS,
) -> ParserSelection:
    """Select a validated parser family.

    Explicit source-series bindings win. If none exists, an exact validated
    schema-fingerprint match can reuse a family. A parser family is a physical
    extraction implementation; its output contract and semantic projector are
    selected separately.
    """
    families = load_families(families_path)
    bindings = [
        row
        for row in _rows(bindings_path)
        if row["source_series_key"] == source_series_key
        and row["binding_status"].startswith("validated")
    ]
    bindings.sort(key=lambda row: int(row["priority"]), reverse=True)

    for row in bindings:
        family = families.get(row["parser_family_code"])
        if family is None:
            raise ValueError(
                f"Binding {source_series_key!r} references unknown parser family "
                f"{row['parser_family_code']!r}"
            )
        if not family.validation_status.startswith("validated"):
            continue
        if (
            family.supported_schema_fingerprints
            and schema_fingerprint not in family.supported_schema_fingerprints
        ):
            continue
        return ParserSelection(
            family=family,
            source_series_key=source_series_key,
            selection_basis=row["selection_basis"],
            priority=int(row["priority"]),
        )

    fingerprint_matches = [
        family
        for family in families.values()
        if family.validation_status.startswith("validated")
        and schema_fingerprint in family.supported_schema_fingerprints
    ]
    if len(fingerprint_matches) == 1:
        return ParserSelection(
            family=fingerprint_matches[0],
            source_series_key=source_series_key,
            selection_basis="exact_schema_fingerprint",
            priority=0,
        )
    if not fingerprint_matches:
        raise LookupError(
            f"No validated parser family for series={source_series_key!r}, "
            f"fingerprint={schema_fingerprint!r}"
        )
    raise LookupError(
        f"Multiple parser families match fingerprint {schema_fingerprint!r}; "
        "add an explicit source-series binding"
    )


def semantic_profile_for_family(
    family: ParserFamily,
    *,
    profiles_path: Path = DEFAULT_SEMANTIC_PROFILES,
) -> SemanticProfile:
    profiles = load_semantic_profiles(profiles_path)
    try:
        profile = profiles[family.semantic_profile_code]
    except KeyError as exc:
        raise LookupError(
            f"Parser family {family.code!r} references unknown semantic profile "
            f"{family.semantic_profile_code!r}"
        ) from exc
    if profile.record_contract_code != family.record_contract_code:
        raise ValueError(
            f"Record-contract mismatch between parser family {family.code!r} "
            f"and semantic profile {profile.code!r}"
        )
    return profile
