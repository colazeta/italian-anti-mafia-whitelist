from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator

from white_list_archive.acquisition.istat_municipalities import (
    iter_municipalities,
    sha256_file,
)

RESOLVER_NAME = "white_list_archive.geography.address_structure"
RESOLVER_VERSION = "1"

TOKEN_RE = re.compile(r"[^\W_]+", re.UNICODE)
LEADING_SEPARATOR_RE = re.compile(r"^[\s,;:\-–—]+")
PROVINCE_MARKER_RE = re.compile(
    r"^\s*(?:\(\s*(?P<paren>[A-Za-z]{2})\s*\)|,\s*(?P<comma>[A-Za-z]{2})\b)"
)
PARENTHETICAL_MARKER_NEAR_START_RE = re.compile(
    r"^\s*.{1,50}?\(\s*(?P<marker>[A-Za-z]{2})\s*\)", re.DOTALL
)
NO_CIVIC_RE = re.compile(
    r"(?:"
    r"\bS\s*\.?\s*N\s*\.?\s*C\s*\.?\b|"
    r"\bS\s*[\./]\s*N\s*\.?\b|"
    r"\bS\s*\.\s*N\s*\.?\b|"
    r"\bSNC\b|"
    r"\bSENZA\s+NUMERO\s+CIVICO\b"
    r")\s*[.,;:\-]*\s*$",
    re.IGNORECASE,
)
ROUTE_KM_RE = re.compile(
    r"\b(?:KM|CHILOMETRO|CHILOMETRICA)\s*[.:]?\s*\d", re.IGNORECASE
)
ROUTE_RE = re.compile(
    r"\b(?:S\s*\.?\s*S\s*\.?|S\s*\.?\s*P\s*\.?|"
    r"STRADA\s+STATALE|STRADA\s+PROVINCIALE)\b",
    re.IGNORECASE,
)
EXPLICIT_CIVIC_PREFIX_RE = re.compile(r"(?:\bN\s*[.°º]?\s*)$", re.IGNORECASE)
CIVIC_RE = re.compile(
    r"(?P<separator>[,;:]?\s*)"
    r"(?P<prefix>N\s*[.°º]?\s*)?"
    r"(?P<number>\d{1,4})"
    r"(?:\s*(?:/|-)\s*(?P<slash_exp>[A-Za-z]{1,3})|"
    r"\s+(?P<word_exp>BIS|TER|QUATER))?"
    r"\s*[.,;:]?\s*$",
    re.IGNORECASE,
)

LEADING_ODONYM_ALIASES: tuple[tuple[tuple[str, ...], tuple[str, ...]], ...] = (
    (("C", "DA"), ("CONTRADA",)),
    (("CDA",), ("CONTRADA",)),
    (("V",), ("VIA",)),
    (("VLE",), ("VIALE",)),
    (("V", "LE"), ("VIALE",)),
    (("PZZA",), ("PIAZZA",)),
    (("P", "ZZA"), ("PIAZZA",)),
    (("CSO",), ("CORSO",)),
    (("C", "SO"), ("CORSO",)),
    (("LGO",), ("LARGO",)),
    (("L", "GO"), ("LARGO",)),
    (("LOC",), ("LOCALITA",)),
    (("LOC", "TA"), ("LOCALITA",)),
)

RESOLVER_CONFIGURATION = json.dumps(
    {
        "version": RESOLVER_VERSION,
        "municipality": {
            "method": "longest official Istat municipality-name token prefix",
            "aliases": ["municipality_name_it", "municipality_name_other", "municipality_name"],
            "province_marker": "optional two-letter marker after matched municipality",
            "mismatch_policy": "requires_review",
            "fuzzy_matching": False,
        },
        "civic": {
            "terminal_numeric_digits": "1-4",
            "terminal_5_digit_values": "never treated as civic",
            "snc": "explicit no-civic marker",
            "route_km": "requires_review; never auto-read as civic",
        },
        "principle": "source-structure parsing only; no ANNCSU match or geocode assertion",
    },
    sort_keys=True,
    ensure_ascii=False,
)
RESOLVER_CONFIGURATION_HASH = hashlib.sha256(
    RESOLVER_CONFIGURATION.encode("utf-8")
).hexdigest()


@dataclass(frozen=True)
class Token:
    raw: str
    folded: str
    start: int
    end: int


@dataclass(frozen=True)
class MunicipalityAlias:
    tokens: tuple[str, ...]
    record: dict[str, str]


def fold_token(value: str) -> str:
    value = unicodedata.normalize("NFKD", value)
    value = "".join(char for char in value if not unicodedata.combining(char))
    return "".join(char for char in value.upper() if char.isalnum())


def tokenize(value: str) -> list[Token]:
    output: list[Token] = []
    for match in TOKEN_RE.finditer(unicodedata.normalize("NFKC", value or "")):
        raw = match.group(0)
        folded = fold_token(raw)
        if folded:
            output.append(Token(raw=raw, folded=folded, start=match.start(), end=match.end()))
    return output


def normalise_odonym_key(value: str) -> str:
    tokens = [token.folded for token in tokenize(value)]
    if not tokens:
        return ""
    for source, replacement in LEADING_ODONYM_ALIASES:
        if tuple(tokens[: len(source)]) == source:
            tokens = list(replacement) + tokens[len(source) :]
            break
    return " ".join(tokens)


def _record_aliases(record: dict[str, str]) -> set[tuple[str, ...]]:
    aliases: set[tuple[str, ...]] = set()
    for field in ("municipality_name_it", "municipality_name_other", "municipality_name"):
        value = (record.get(field) or "").strip()
        if not value:
            continue
        tokens = tuple(token.folded for token in tokenize(value))
        if tokens:
            aliases.add(tokens)
    return aliases


class MunicipalityResolver:
    """Resolve only exact official municipality-name prefixes.

    This layer deliberately performs no edit-distance, phonetic or embedding match.
    Ambiguity and source/Istat province conflicts are surfaced for review.
    """

    def __init__(self, records: Iterable[dict[str, str]]):
        self.records_by_code: dict[str, dict[str, str]] = {}
        self.aliases_by_first_token: dict[str, list[MunicipalityAlias]] = defaultdict(list)
        self.province_plates: set[str] = set()

        seen_alias_record: set[tuple[tuple[str, ...], str]] = set()
        for source_record in records:
            record = {key: value or "" for key, value in source_record.items()}
            municipality_code = record.get("municipality_code", "").strip()
            if not municipality_code:
                raise ValueError("Municipality record missing municipality_code")
            if municipality_code in self.records_by_code:
                raise ValueError(f"Duplicate municipality code in resolver: {municipality_code}")
            self.records_by_code[municipality_code] = record
            plate = record.get("province_plate", "").strip().upper()
            if plate:
                self.province_plates.add(plate)
            for alias_tokens in _record_aliases(record):
                dedup_key = (alias_tokens, municipality_code)
                if dedup_key in seen_alias_record:
                    continue
                seen_alias_record.add(dedup_key)
                self.aliases_by_first_token[alias_tokens[0]].append(
                    MunicipalityAlias(tokens=alias_tokens, record=record)
                )

        for values in self.aliases_by_first_token.values():
            values.sort(key=lambda alias: (-len(alias.tokens), alias.record["municipality_code"]))

    def resolve(self, raw_address: str) -> dict[str, object]:
        raw_address = unicodedata.normalize("NFKC", raw_address or "").strip()
        source_tokens = tokenize(raw_address)
        if not source_tokens:
            return self._unresolved(raw_address, "BLANK", [])

        possible = self.aliases_by_first_token.get(source_tokens[0].folded, [])
        matches: list[MunicipalityAlias] = []
        for alias in possible:
            if len(source_tokens) < len(alias.tokens):
                continue
            if tuple(token.folded for token in source_tokens[: len(alias.tokens)]) == alias.tokens:
                matches.append(alias)
        if not matches:
            marker_match = PARENTHETICAL_MARKER_NEAR_START_RE.search(raw_address)
            marker = marker_match.group("marker").upper() if marker_match else ""
            status = "UNRESOLVED_WITH_MARKER" if marker else "UNRESOLVED"
            return self._unresolved(raw_address, status, [], source_marker=marker)

        longest = max(len(alias.tokens) for alias in matches)
        longest_matches = [alias for alias in matches if len(alias.tokens) == longest]
        by_code = {
            alias.record["municipality_code"]: alias for alias in longest_matches
        }
        candidates = list(by_code.values())

        municipality_end = source_tokens[longest - 1].end
        suffix = raw_address[municipality_end:]
        marker, marker_end = _extract_province_marker(suffix)

        if len(candidates) > 1 and marker:
            marker_filtered = [
                alias
                for alias in candidates
                if alias.record.get("province_plate", "").strip().upper() == marker
            ]
            if len(marker_filtered) == 1:
                candidates = marker_filtered

        if len(candidates) != 1:
            return self._unresolved(
                raw_address,
                "AMBIGUOUS",
                [alias.record["municipality_code"] for alias in candidates],
                source_marker=marker,
            )

        record = candidates[0].record
        province_plate = record.get("province_plate", "").strip().upper()
        remainder = suffix[marker_end:] if marker_end else suffix
        remainder = LEADING_SEPARATOR_RE.sub("", remainder).strip()
        status = "EXACT"
        review_reason = ""
        if marker and province_plate and marker != province_plate:
            status = "PROVINCE_MISMATCH_REVIEW"
            review_reason = f"source marker {marker} != Istat province plate {province_plate}"

        return {
            "municipality_status": status,
            "municipality_match_method": "official_name_prefix_exact",
            "municipality_name": record.get("municipality_name_it") or record.get("municipality_name") or "",
            "municipality_code": record.get("municipality_code", ""),
            "cadastral_code": record.get("cadastral_code", ""),
            "province_plate": province_plate,
            "region_code": record.get("region_code", ""),
            "region_name": record.get("region_name", ""),
            "supra_unit_code": record.get("supra_unit_code", ""),
            "supra_unit_name": record.get("supra_unit_name", ""),
            "supra_unit_type_code": record.get("supra_unit_type_code", ""),
            "nuts1_2024": record.get("nuts1_2024", ""),
            "nuts2_2024": record.get("nuts2_2024", ""),
            "nuts3_2024": record.get("nuts3_2024", ""),
            "source_province_marker": marker,
            "municipality_remainder_raw": remainder,
            "municipality_candidate_codes": [record.get("municipality_code", "")],
            "municipality_review_reason": review_reason,
        }

    @staticmethod
    def _unresolved(
        raw_address: str,
        status: str,
        candidates: list[str],
        *,
        source_marker: str = "",
    ) -> dict[str, object]:
        return {
            "municipality_status": status,
            "municipality_match_method": "",
            "municipality_name": "",
            "municipality_code": "",
            "cadastral_code": "",
            "province_plate": "",
            "region_code": "",
            "region_name": "",
            "supra_unit_code": "",
            "supra_unit_name": "",
            "supra_unit_type_code": "",
            "nuts1_2024": "",
            "nuts2_2024": "",
            "nuts3_2024": "",
            "source_province_marker": source_marker,
            "municipality_remainder_raw": raw_address,
            "municipality_candidate_codes": candidates,
            "municipality_review_reason": "",
        }


def _extract_province_marker(suffix: str) -> tuple[str, int]:
    match = PROVINCE_MARKER_RE.match(suffix)
    if not match:
        return "", 0
    marker = (match.group("paren") or match.group("comma") or "").upper()
    return marker, match.end()


def parse_remainder(remainder_raw: str) -> dict[str, object]:
    remainder = unicodedata.normalize("NFKC", remainder_raw or "").strip()
    remainder = LEADING_SEPARATOR_RE.sub("", remainder).strip()
    if not remainder:
        return {
            "street_raw": "",
            "odonym_key": "",
            "civic_number": "",
            "civic_exponent": "",
            "no_civic_marker": False,
            "structure_status": "MUNICIPALITY_ONLY",
            "structure_review_reason": "",
        }

    no_civic = NO_CIVIC_RE.search(remainder)
    if no_civic:
        street_raw = remainder[: no_civic.start()].rstrip(" ,;:-")
        return {
            "street_raw": street_raw,
            "odonym_key": normalise_odonym_key(street_raw),
            "civic_number": "",
            "civic_exponent": "",
            "no_civic_marker": True,
            "structure_status": "STRUCTURED_STREET_NO_CIVIC",
            "structure_review_reason": "explicit source no-civic marker",
        }

    if ROUTE_KM_RE.search(remainder):
        return {
            "street_raw": remainder,
            "odonym_key": normalise_odonym_key(remainder),
            "civic_number": "",
            "civic_exponent": "",
            "no_civic_marker": False,
            "structure_status": "ROUTE_KM_REQUIRES_REVIEW",
            "structure_review_reason": "route kilometre notation must not be treated as a civic number",
        }

    civic = CIVIC_RE.search(remainder)
    if civic:
        prefix_start = civic.start("prefix") if civic.group("prefix") else None
        number_start = civic.start("number")
        separator = civic.group("separator") or ""
        explicit_prefix = bool(civic.group("prefix"))
        explicit_separator = any(char in separator for char in ",;:")
        street_raw = remainder[: civic.start()].rstrip(" ,;:-")
        if not street_raw:
            return {
                "street_raw": remainder,
                "odonym_key": normalise_odonym_key(remainder),
                "civic_number": "",
                "civic_exponent": "",
                "no_civic_marker": False,
                "structure_status": "CIVIC_WITHOUT_ODONYM_REQUIRES_REVIEW",
                "structure_review_reason": "terminal number found without an odonym prefix",
            }
        if ROUTE_RE.search(street_raw) and not (explicit_prefix or explicit_separator):
            return {
                "street_raw": remainder,
                "odonym_key": normalise_odonym_key(remainder),
                "civic_number": "",
                "civic_exponent": "",
                "no_civic_marker": False,
                "structure_status": "ROUTE_NUMBER_REQUIRES_REVIEW",
                "structure_review_reason": "terminal route number is not safely distinguishable from a civic number",
            }
        exponent = (civic.group("slash_exp") or civic.group("word_exp") or "").upper()
        return {
            "street_raw": street_raw,
            "odonym_key": normalise_odonym_key(street_raw),
            "civic_number": civic.group("number"),
            "civic_exponent": exponent,
            "no_civic_marker": False,
            "structure_status": "STRUCTURED_CIVIC_CANDIDATE",
            "structure_review_reason": "",
        }

    return {
        "street_raw": remainder,
        "odonym_key": normalise_odonym_key(remainder),
        "civic_number": "",
        "civic_exponent": "",
        "no_civic_marker": False,
        "structure_status": "STRUCTURED_STREET_ONLY",
        "structure_review_reason": "",
    }


def resolve_source_address(raw_address: str, resolver: MunicipalityResolver) -> dict[str, object]:
    municipality = resolver.resolve(raw_address)
    municipality_status = str(municipality["municipality_status"])
    if municipality_status == "EXACT":
        structure = parse_remainder(str(municipality["municipality_remainder_raw"]))
    elif municipality_status == "PROVINCE_MISMATCH_REVIEW":
        structure = parse_remainder(str(municipality["municipality_remainder_raw"]))
        structure["structure_status"] = "MUNICIPALITY_REQUIRES_REVIEW"
        structure["structure_review_reason"] = str(municipality["municipality_review_reason"])
    elif municipality_status == "UNRESOLVED_WITH_MARKER":
        structure = {
            "street_raw": "",
            "odonym_key": "",
            "civic_number": "",
            "civic_exponent": "",
            "no_civic_marker": False,
            "structure_status": "NON_ITALIAN_OR_UNRESOLVED_WITH_MARKER",
            "structure_review_reason": "two-letter parenthetical marker is not interpreted as a country code automatically",
        }
    elif municipality_status == "BLANK":
        structure = {
            "street_raw": "",
            "odonym_key": "",
            "civic_number": "",
            "civic_exponent": "",
            "no_civic_marker": False,
            "structure_status": "BLANK_ADDRESS",
            "structure_review_reason": "",
        }
    else:
        structure = {
            "street_raw": "",
            "odonym_key": "",
            "civic_number": "",
            "civic_exponent": "",
            "no_civic_marker": False,
            "structure_status": "MUNICIPALITY_UNRESOLVED",
            "structure_review_reason": "",
        }
    return {**municipality, **structure}


def _load_istat_manifest(path: Path) -> tuple[list[dict[str, str]], dict[str, object], str]:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("provider") != "ISTAT":
        raise ValueError("Municipality resolver requires an ISTAT crosswalk manifest")
    crosswalk = manifest.get("crosswalk_csv")
    if not isinstance(crosswalk, dict):
        raise ValueError("Istat manifest missing crosswalk_csv")
    relative_path = crosswalk.get("path")
    expected_sha = crosswalk.get("sha256")
    if not relative_path or not expected_sha:
        raise ValueError("Istat manifest missing crosswalk path/SHA-256")
    csv_path = path.parent / str(relative_path)
    observed_sha = sha256_file(csv_path)
    if observed_sha.lower() != str(expected_sha).lower():
        raise ValueError(
            f"Istat crosswalk SHA-256 mismatch: expected {expected_sha}, observed {observed_sha}"
        )
    return list(iter_municipalities(csv_path)), manifest, observed_sha


OUTPUT_FIELDS = (
    "row_ordinal",
    "mention_key",
    "registered_office_raw",
    "municipality_status",
    "municipality_match_method",
    "municipality_name",
    "municipality_code",
    "cadastral_code",
    "province_plate",
    "region_code",
    "region_name",
    "supra_unit_code",
    "supra_unit_name",
    "supra_unit_type_code",
    "nuts1_2024",
    "nuts2_2024",
    "nuts3_2024",
    "source_province_marker",
    "municipality_remainder_raw",
    "municipality_candidate_codes_json",
    "municipality_review_reason",
    "street_raw",
    "odonym_key",
    "civic_number",
    "civic_exponent",
    "no_civic_marker",
    "structure_status",
    "structure_review_reason",
)


def resolve_csv(
    records_path: Path,
    istat_manifest_path: Path,
    output_dir: Path,
    *,
    address_column: str = "registered_office_raw",
) -> dict[str, object]:
    municipality_records, istat_manifest, crosswalk_sha = _load_istat_manifest(istat_manifest_path)
    resolver = MunicipalityResolver(municipality_records)
    output_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, object]] = []
    raw_addresses: list[str] = []
    with records_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if address_column not in (reader.fieldnames or []):
            raise ValueError(f"Input CSV missing address column {address_column!r}")
        for source_row in reader:
            raw = (source_row.get(address_column) or "").strip()
            raw_addresses.append(raw)
            resolved = resolve_source_address(raw, resolver)
            rows.append(
                {
                    "row_ordinal": source_row.get("row_ordinal", ""),
                    "mention_key": source_row.get("mention_key", ""),
                    "registered_office_raw": raw,
                    **resolved,
                }
            )

    csv_path = output_dir / "address_structure.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_FIELDS, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            materialised = dict(row)
            materialised["municipality_candidate_codes_json"] = json.dumps(
                row.get("municipality_candidate_codes", []), ensure_ascii=False
            )
            materialised["no_civic_marker"] = "true" if row.get("no_civic_marker") else "false"
            writer.writerow(materialised)

    municipality_counts = Counter(str(row["municipality_status"]) for row in rows)
    structure_counts = Counter(str(row["structure_status"]) for row in rows)
    region_counts = Counter(
        str(row["region_name"])
        for row in rows
        if row["municipality_status"] == "EXACT" and row.get("region_name")
    )
    province_counts = Counter(
        str(row["province_plate"])
        for row in rows
        if row["municipality_status"] == "EXACT" and row.get("province_plate")
    )
    exact_municipalities = Counter(
        (str(row["municipality_code"]), str(row["municipality_name"]))
        for row in rows
        if row["municipality_status"] == "EXACT"
    )
    report = {
        "resolver_name": RESOLVER_NAME,
        "resolver_version": RESOLVER_VERSION,
        "resolver_configuration_hash": RESOLVER_CONFIGURATION_HASH,
        "input_records_path": str(records_path),
        "input_record_count": len(rows),
        "nonblank_address_count": sum(bool(value) for value in raw_addresses),
        "unique_nonblank_address_count": len({value for value in raw_addresses if value}),
        "istat_provider_version": istat_manifest.get("provider_version"),
        "istat_crosswalk_sha256": crosswalk_sha,
        "municipality_status_counts": dict(sorted(municipality_counts.items())),
        "structure_status_counts": dict(sorted(structure_counts.items())),
        "resolved_region_counts": dict(sorted(region_counts.items())),
        "resolved_province_counts": dict(sorted(province_counts.items())),
        "top_resolved_municipalities": [
            {"municipality_code": code, "municipality_name": name, "count": count}
            for (code, name), count in exact_municipalities.most_common(50)
        ],
        "output_csv": csv_path.name,
        "output_csv_sha256": sha256_file(csv_path),
    }
    report_path = output_dir / "address_structure_report.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Deterministically resolve White List source-address structure against Istat municipalities."
    )
    parser.add_argument("--records", type=Path, required=True)
    parser.add_argument("--istat-manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--address-column", default="registered_office_raw")
    args = parser.parse_args()
    report = resolve_csv(
        args.records,
        args.istat_manifest,
        args.output_dir,
        address_column=args.address_column,
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
