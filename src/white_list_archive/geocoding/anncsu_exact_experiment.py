from __future__ import annotations

import argparse
import csv
import json
import re
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import psycopg
except ImportError as exc:  # pragma: no cover
    psycopg = None
    _IMPORT_ERROR = exc
else:
    _IMPORT_ERROR = None

from white_list_archive.acquisition.anncsu import iter_anncsu_rows, parse_decimal_coordinate
from .structured_query import MunicipalityPrefixMatcher

TOKEN_RE = re.compile(r"[^\W_]+", re.UNICODE)
TERMINAL_CIVIC_RE = re.compile(
    r"^(?P<street>.*?)(?:,\s*|\s+)(?P<number>\d{1,5})(?:\s*(?:/|-)\s*(?P<exponent>[A-Za-z]))?\s*$"
)
NO_CIVIC_RE = re.compile(
    r"(?:\bS\s*\.?\s*N\s*\.?\s*C\s*\.?\b|\bS\s*\.?\s*N\s*\.?\b)\s*$",
    re.IGNORECASE,
)

# Canonicalise only the road-type spelling. The road type remains part of the
# key so e.g. VIA ROMA cannot silently match PIAZZA ROMA in the same Comune.
ROAD_TYPE_PREFIXES = (
    (("strada", "statale"), "ss"),
    (("s", "s"), "ss"),
    (("ss",), "ss"),
    (("strada", "provinciale"), "sp"),
    (("s", "p"), "sp"),
    (("sp",), "sp"),
    (("c", "da"), "contrada"),
    (("cda",), "contrada"),
    (("contrada",), "contrada"),
    (("p", "zza"), "piazza"),
    (("pzza",), "piazza"),
    (("piazza",), "piazza"),
    (("piazzale",), "piazzale"),
    (("localita",), "localita"),
    (("loc",), "localita"),
    (("frazione",), "frazione"),
    (("fraz",), "frazione"),
    (("viale",), "viale"),
    (("via",), "via"),
    (("corso",), "corso"),
    (("strada",), "strada"),
    (("vicolo",), "vicolo"),
    (("vico",), "vico"),
    (("largo",), "largo"),
    (("rione",), "rione"),
)
ROUTE_TRAILING_PREFIXES = {
    ("ss",),
    ("sp",),
    ("s", "s"),
    ("s", "p"),
    ("strada", "statale"),
    ("strada", "provinciale"),
    ("km",),
}


def _fold(value: str) -> str:
    text = unicodedata.normalize("NFKD", value or "")
    text = "".join(char for char in text if not unicodedata.combining(char))
    return text.casefold()


def _tokens(value: str) -> list[str]:
    return [_fold(match.group(0)) for match in TOKEN_RE.finditer(value or "")]


def canonical_street_key(value: str) -> str:
    """Return a conservative road-type-preserving street key.

    This normalises punctuation, case, diacritics and a small set of explicit
    road-type abbreviations. It deliberately does not drop road type and does
    not use fuzzy/edit-distance matching.
    """
    tokens = _tokens(value)
    if not tokens:
        return ""
    road_type = "unspecified"
    name_tokens = tokens
    for prefix, canonical_type in ROAD_TYPE_PREFIXES:
        if tuple(tokens[: len(prefix)]) == prefix:
            road_type = canonical_type
            name_tokens = tokens[len(prefix) :]
            break
    if not name_tokens:
        return ""
    return road_type + "|" + " ".join(name_tokens)


@dataclass(frozen=True)
class CivicParse:
    street_text: str
    status: str
    number: str | None = None
    exponent: str | None = None


def parse_source_street_and_civic(value: str) -> CivicParse:
    text = (value or "").strip()
    if not text:
        return CivicParse("", "blank")
    no_civic = NO_CIVIC_RE.search(text)
    if no_civic:
        return CivicParse(text[: no_civic.start()].rstrip(" ,;-"), "explicit_no_civic")

    match = TERMINAL_CIVIC_RE.fullmatch(text)
    if not match:
        return CivicParse(text, "no_confident_terminal_civic")
    street = match.group("street").rstrip(" ,;-")
    number = str(int(match.group("number")))
    exponent = (match.group("exponent") or "").upper() or None

    street_tokens = _tokens(street)
    for route_prefix in ROUTE_TRAILING_PREFIXES:
        if len(street_tokens) >= len(route_prefix) and tuple(
            street_tokens[-len(route_prefix) :]
        ) == route_prefix:
            return CivicParse(text, "terminal_number_is_route_number")
    return CivicParse(street, "civic", number, exponent)


def _normalise_anncsu_number(value: str) -> str | None:
    text = (value or "").strip()
    if not text:
        return None
    if text.isdigit():
        return str(int(text))
    match = re.fullmatch(r"0*(\d+)(?:[.,]0+)?", text)
    return str(int(match.group(1))) if match else text.casefold()


def _normalise_exponent(value: str) -> str | None:
    text = (value or "").strip().upper()
    return text or None


def _select_addresses(dsn: str) -> list[str]:
    if psycopg is None:
        raise RuntimeError("Install the project with the database extra") from _IMPORT_ERROR
    with psycopg.connect(dsn) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT DISTINCT btrim(full_address) FROM core.address "
            "WHERE btrim(full_address) <> '' ORDER BY 1"
        )
        return [str(row[0]) for row in cur.fetchall()]


def run_experiment(
    *,
    dsn: str,
    istat_csv: Path,
    anncsu_csv: Path,
    output_dir: Path,
) -> dict[str, Any]:
    addresses = _select_addresses(dsn)
    matcher = MunicipalityPrefixMatcher.from_istat_csv(istat_csv)
    prepared: list[dict[str, Any]] = []
    wanted: dict[str, set[str]] = defaultdict(set)
    prepared_calabria_count = 0
    for address in addresses:
        split = matcher.split(address)
        if split.status != "structured" or split.query is None:
            prepared.append({"source_address": address, "status": split.status})
            continue
        query = split.query
        if _fold(query.region_name) != "calabria":
            prepared.append(
                {
                    "source_address": address,
                    "status": "outside_calabria",
                    "city": query.city,
                    "region": query.region_name,
                }
            )
            continue
        civic = parse_source_street_and_civic(query.street)
        street_key = canonical_street_key(civic.street_text)
        if not query.cadastral_code:
            prepared.append({"source_address": address, "status": "missing_cadastral_code"})
            continue
        if not street_key:
            prepared.append({"source_address": address, "status": "empty_street_key"})
            continue
        item = {
            "source_address": address,
            "status": "prepared",
            "city": query.city,
            "region": query.region_name,
            "cadastral_code": query.cadastral_code,
            "source_street": query.street,
            "street_text": civic.street_text,
            "street_key": street_key,
            "civic_parse_status": civic.status,
            "source_civic": civic.number,
            "source_exponent": civic.exponent,
        }
        prepared.append(item)
        prepared_calabria_count += 1
        wanted[query.cadastral_code].add(street_key)

    anncsu_index: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    scanned = 0
    retained = 0
    for row in iter_anncsu_rows(anncsu_csv):
        scanned += 1
        cadastral = (row.get("CODICE_COMUNE") or "").strip().upper()
        wanted_keys = wanted.get(cadastral)
        if not wanted_keys:
            continue
        keys = {
            canonical_street_key(row.get("DIZIONE_LINGUA1") or ""),
            canonical_street_key(row.get("ODONIMO") or ""),
        }
        keys.discard("")
        for key in keys & wanted_keys:
            anncsu_index[(cadastral, key)].append(row)
            retained += 1

    outcome_counts = Counter()
    method_counts = Counter()
    results: list[dict[str, Any]] = []
    for item in prepared:
        if item.get("status") != "prepared":
            outcome_counts[item["status"]] += 1
            results.append(item)
            continue
        rows = anncsu_index.get((item["cadastral_code"], item["street_key"]), [])
        if not rows:
            item["status"] = "no_exact_street_match"
            outcome_counts[item["status"]] += 1
            results.append(item)
            continue

        item["anncsu_matching_access_rows"] = len(rows)
        source_civic = item.get("source_civic")
        if not source_civic:
            item["status"] = "exact_street_without_confident_civic"
            outcome_counts[item["status"]] += 1
            results.append(item)
            continue

        exact = [
            row
            for row in rows
            if _normalise_anncsu_number(row.get("CIVICO") or "") == source_civic
            and _normalise_exponent(row.get("ESPONENTE") or "") == item.get("source_exponent")
        ]
        if not exact:
            item["status"] = "exact_street_civic_not_found"
            outcome_counts[item["status"]] += 1
            results.append(item)
            continue

        identities: dict[tuple[str, str, str, str], dict[str, str]] = {}
        for row in exact:
            identity = (
                (row.get("PROGRESSIVO_ACCESSO") or "").strip(),
                (row.get("COORD_X_COMUNE") or "").strip(),
                (row.get("COORD_Y_COMUNE") or "").strip(),
                (row.get("METODO") or "").strip(),
            )
            identities[identity] = row
        if len(identities) != 1:
            item["status"] = "exact_civic_ambiguous"
            item["anncsu_exact_rows"] = len(exact)
            item["anncsu_unique_access_identities"] = len(identities)
            outcome_counts[item["status"]] += 1
            results.append(item)
            continue

        row = next(iter(identities.values()))
        latitude = parse_decimal_coordinate(row.get("COORD_Y_COMUNE") or "")
        longitude = parse_decimal_coordinate(row.get("COORD_X_COMUNE") or "")
        has_coordinate_pair = latitude is not None and longitude is not None
        status = (
            "exact_civic_unique_with_coordinates"
            if has_coordinate_pair
            else "exact_civic_unique_without_coordinates"
        )
        item.update(
            {
                "status": status,
                "anncsu_exact_rows": len(exact),
                "anncsu_progressivo_nazionale": (row.get("PROGRESSIVO_NAZIONALE") or "").strip(),
                "anncsu_progressivo_accesso": (row.get("PROGRESSIVO_ACCESSO") or "").strip(),
                "anncsu_odonimo": (row.get("ODONIMO") or "").strip(),
                "anncsu_dizione_lingua1": (row.get("DIZIONE_LINGUA1") or "").strip(),
                "anncsu_civico": (row.get("CIVICO") or "").strip(),
                "anncsu_esponente": (row.get("ESPONENTE") or "").strip(),
                "latitude": latitude,
                "longitude": longitude,
                "anncsu_metodo": (row.get("METODO") or "").strip(),
            }
        )
        outcome_counts[status] += 1
        if has_coordinate_pair:
            method_counts[item["anncsu_metodo"] or "UNKNOWN"] += 1
        results.append(item)

    exact_access_unique = (
        outcome_counts["exact_civic_unique_with_coordinates"]
        + outcome_counts["exact_civic_unique_without_coordinates"]
    )
    exact_coordinate = outcome_counts["exact_civic_unique_with_coordinates"]
    exact_street_any = sum(
        count
        for status, count in outcome_counts.items()
        if status in {
            "exact_civic_unique_with_coordinates",
            "exact_civic_unique_without_coordinates",
            "exact_civic_ambiguous",
            "exact_street_civic_not_found",
            "exact_street_without_confident_civic",
        }
    )
    summary = {
        "population_addresses": len(addresses),
        "anncsu_rows_scanned": scanned,
        "anncsu_index_rows_retained": retained,
        "prepared_calabria_addresses": prepared_calabria_count,
        "outcome_counts": dict(sorted(outcome_counts.items())),
        "exact_street_any": exact_street_any,
        "exact_street_any_rate_pct": round(100 * exact_street_any / len(addresses), 2),
        "exact_civic_unique_access": exact_access_unique,
        "exact_civic_unique_access_rate_pct": round(100 * exact_access_unique / len(addresses), 2),
        "exact_civic_unique_with_coordinates": exact_coordinate,
        "exact_civic_unique_with_coordinates_rate_pct": round(100 * exact_coordinate / len(addresses), 2),
        "anncsu_method_counts_for_unique_coordinates": dict(sorted(method_counts.items())),
        "matching_policy": (
            "exact Istat municipality prefix + road-type-preserving exact normalized street key "
            "+ exact terminal civic/exponent + unique ANNCSU access identity; no fuzzy matching"
        ),
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    fields = sorted({key for row in results for key in row})
    with (output_dir / "results.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(results)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Benchmark conservative exact-only linkage of canonical addresses to ANNCSU Calabria."
    )
    parser.add_argument("--dsn", required=True)
    parser.add_argument("--istat-csv", type=Path, required=True)
    parser.add_argument("--anncsu-csv", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    result = run_experiment(
        dsn=args.dsn,
        istat_csv=args.istat_csv,
        anncsu_csv=args.anncsu_csv,
        output_dir=args.output_dir,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
