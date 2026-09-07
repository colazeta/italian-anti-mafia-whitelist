from __future__ import annotations

import re
import statistics
import unicodedata
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from white_list_archive.acquisition.anncsu import iter_anncsu_rows, parse_decimal_coordinate
from .italian_address import MunicipalityPrefixMatcher
from .models import GeocodeCandidate

TOKEN_RE = re.compile(r"[^\W_]+", re.UNICODE)
TERMINAL_CIVIC_RE = re.compile(
    r"^(?P<street>.*?)(?:,\s*|\s+)(?P<number>\d{1,5})(?:\s*(?:/|-)\s*(?P<exponent>[A-Za-z]))?\s*$"
)
NO_CIVIC_RE = re.compile(
    r"(?:\bS\s*\.?\s*N\s*\.?\s*C\s*\.?\b|\bS\s*\.?\s*N\s*\.?\b)\s*$",
    re.IGNORECASE,
)

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

ANNCSU_ATTRIBUTION = "ANNCSU — Istat e Agenzia delle Entrate"
ANNCSU_LICENCE = "CC-BY 4.0"


def _fold(value: str) -> str:
    text = unicodedata.normalize("NFKD", value or "")
    text = "".join(char for char in text if not unicodedata.combining(char))
    return text.casefold()


def _tokens(value: str) -> list[str]:
    return [_fold(match.group(0)) for match in TOKEN_RE.finditer(value or "")]


def canonical_street_key(value: str) -> str:
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


def parse_street_and_civic(value: str) -> CivicParse:
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
        if len(street_tokens) >= len(route_prefix) and tuple(street_tokens[-len(route_prefix) :]) == route_prefix:
            return CivicParse(text, "terminal_number_is_route_number")
    return CivicParse(street, "civic", number, exponent)


def _normalise_number(value: str) -> str | None:
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


def _coordinate_pair(row: dict[str, str]) -> tuple[float, float] | None:
    latitude = parse_decimal_coordinate(row.get("COORD_Y_COMUNE") or "")
    longitude = parse_decimal_coordinate(row.get("COORD_X_COMUNE") or "")
    if latitude is None or longitude is None:
        return None
    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        return None
    return latitude, longitude


def _street_identity(row: dict[str, str]) -> str:
    return (row.get("PROGRESSIVO_NAZIONALE") or "").strip()


def _official_street_name(rows: list[dict[str, str]]) -> str:
    values = {(row.get("ODONIMO") or "").strip() for row in rows}
    values.discard("")
    return min(values, key=lambda value: (len(value), value)) if values else ""


def _matched_label(street_name: str, civic: str | None, exponent: str | None, city: str) -> str:
    civic_text = ""
    if civic:
        civic_text = " " + civic + (("/" + exponent) if exponent else "")
    return ", ".join(part for part in (street_name + civic_text, city, "Italia") if part)


@dataclass(frozen=True)
class AnncsuResolution:
    source_address: str
    status: str
    candidate: GeocodeCandidate | None
    municipality_code: str | None
    cadastral_code: str | None
    detail: dict[str, Any]


@dataclass(frozen=True)
class _PreparedAddress:
    source_address: str
    municipality_code: str
    cadastral_code: str
    city: str
    province_plate: str
    region_name: str
    source_remainder: str
    civic: CivicParse
    street_key: str


def resolve_anncsu_addresses(
    source_addresses: Iterable[str],
    *,
    municipality_matcher: MunicipalityPrefixMatcher,
    anncsu_csv: Path,
    dataset_region_name: str = "Calabria",
) -> list[AnncsuResolution]:
    source_addresses = list(source_addresses)
    prepared: list[_PreparedAddress] = []
    terminal: dict[str, AnncsuResolution] = {}
    wanted: dict[str, set[str]] = defaultdict(set)

    for source_address in source_addresses:
        result = municipality_matcher.split(source_address)
        if result.status != "exact" or result.split is None:
            terminal[source_address] = AnncsuResolution(source_address, result.status, None, None, None, {"split_detail": result.detail})
            continue
        split = result.split
        municipality = split.municipality
        if _fold(municipality.region_name) != _fold(dataset_region_name):
            terminal[source_address] = AnncsuResolution(source_address, "outside_dataset_region", None, municipality.municipality_code, municipality.cadastral_code, {"region_name": municipality.region_name})
            continue
        civic = parse_street_and_civic(split.remainder)
        street_key = canonical_street_key(civic.street_text)
        if not street_key:
            terminal[source_address] = AnncsuResolution(source_address, "empty_street_key", None, municipality.municipality_code, municipality.cadastral_code, {"civic_parse_status": civic.status})
            continue
        item = _PreparedAddress(
            source_address=source_address,
            municipality_code=municipality.municipality_code,
            cadastral_code=municipality.cadastral_code,
            city=municipality.display_name,
            province_plate=municipality.province_plate,
            region_name=municipality.region_name,
            source_remainder=split.remainder,
            civic=civic,
            street_key=street_key,
        )
        prepared.append(item)
        wanted[item.cadastral_code].add(street_key)

    anncsu_index: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in iter_anncsu_rows(anncsu_csv):
        cadastral_code = (row.get("CODICE_COMUNE") or "").strip().upper()
        wanted_keys = wanted.get(cadastral_code)
        if not wanted_keys:
            continue
        key = canonical_street_key(row.get("ODONIMO") or "")
        if key and key in wanted_keys:
            anncsu_index[(cadastral_code, key)].append(row)

    resolved: dict[str, AnncsuResolution] = dict(terminal)
    for item in prepared:
        rows = anncsu_index.get((item.cadastral_code, item.street_key), [])
        if not rows:
            resolved[item.source_address] = AnncsuResolution(item.source_address, "no_exact_street_match", None, item.municipality_code, item.cadastral_code, {"street_key": item.street_key, "civic_parse_status": item.civic.status})
            continue

        street_ids = {_street_identity(row) for row in rows if _street_identity(row)}
        if len(street_ids) != 1:
            resolved[item.source_address] = AnncsuResolution(item.source_address, "exact_street_ambiguous", None, item.municipality_code, item.cadastral_code, {"street_key": item.street_key, "street_identity_count": len(street_ids)})
            continue
        street_id = next(iter(street_ids))
        official_street = _official_street_name(rows)
        coordinate_pairs = [pair for row in rows if (pair := _coordinate_pair(row)) is not None]
        street_coordinate = None
        if coordinate_pairs:
            street_coordinate = (
                float(statistics.median(pair[0] for pair in coordinate_pairs)),
                float(statistics.median(pair[1] for pair in coordinate_pairs)),
            )

        source_civic = item.civic.number
        exact_access_rows: list[dict[str, str]] = []
        if source_civic:
            exact_access_rows = [
                row for row in rows
                if _normalise_number(row.get("CIVICO") or "") == source_civic
                and _normalise_exponent(row.get("ESPONENTE") or "") == item.civic.exponent
            ]

        access_identities = {
            (
                (row.get("PROGRESSIVO_ACCESSO") or "").strip(),
                (row.get("COORD_X_COMUNE") or "").strip(),
                (row.get("COORD_Y_COMUNE") or "").strip(),
                (row.get("METODO") or "").strip(),
            ): row
            for row in exact_access_rows
        }

        direct_row = next(iter(access_identities.values())) if len(access_identities) == 1 else None
        direct_coordinate = _coordinate_pair(direct_row) if direct_row else None
        if direct_row and direct_coordinate:
            latitude, longitude = direct_coordinate
            provider_result_id = "access:" + (direct_row.get("PROGRESSIVO_ACCESSO") or "").strip()
            precision = "civic_access"
            status = "exact_civic_with_coordinates"
            coordinate_derivation = "provider_civic_access"
            house_number = source_civic
            exponent = item.civic.exponent
            matched_address = _matched_label(official_street, house_number, exponent, item.city)
        elif direct_row:
            provider_result_id = "access:" + (direct_row.get("PROGRESSIVO_ACCESSO") or "").strip()
            house_number = source_civic
            exponent = item.civic.exponent
            matched_address = _matched_label(official_street, house_number, exponent, item.city)
            if street_coordinate:
                latitude, longitude = street_coordinate
                precision = "street"
                status = "exact_civic_street_coordinate_fallback"
                coordinate_derivation = "median_of_anncsu_street_access_coordinates"
            else:
                latitude = longitude = None
                precision = None
                status = "exact_civic_without_coordinates"
                coordinate_derivation = None
        elif len(access_identities) > 1:
            resolved[item.source_address] = AnncsuResolution(item.source_address, "exact_civic_ambiguous", None, item.municipality_code, item.cadastral_code, {"street_id": street_id, "street_name": official_street, "access_identity_count": len(access_identities), "source_civic": source_civic, "source_exponent": item.civic.exponent})
            continue
        else:
            house_number = None
            exponent = None
            matched_address = _matched_label(official_street, None, None, item.city)
            provider_result_id = "street:" + street_id
            if street_coordinate:
                latitude, longitude = street_coordinate
                precision = "street"
                status = "exact_street_no_confident_civic" if not source_civic else "exact_street_civic_not_found"
                coordinate_derivation = "median_of_anncsu_street_access_coordinates"
            else:
                latitude = longitude = None
                precision = "street"
                status = "exact_street_without_coordinates"
                coordinate_derivation = None

        payload: dict[str, Any] = {
            "resolution_status": status,
            "matching_policy": "istat_exact_prefix+anncsu_odonimo_exact_typed_street+exact_civic_when_available",
            "municipality_code": item.municipality_code,
            "cadastral_code": item.cadastral_code,
            "province_plate": item.province_plate,
            "region_name": item.region_name,
            "street_key": item.street_key,
            "street_id": street_id,
            "civic_parse_status": item.civic.status,
            "source_remainder": item.source_remainder,
            "street_coordinate_access_count": len(coordinate_pairs),
            "coordinate_derivation": coordinate_derivation,
        }
        if direct_row:
            payload.update({
                "access_id": (direct_row.get("PROGRESSIVO_ACCESSO") or "").strip(),
                "anncsu_metodo": (direct_row.get("METODO") or "").strip(),
                "anncsu_civico": (direct_row.get("CIVICO") or "").strip(),
                "anncsu_esponente": (direct_row.get("ESPONENTE") or "").strip(),
            })

        candidate = GeocodeCandidate(
            provider_result_id=provider_result_id,
            candidate_rank=1,
            matched_address=matched_address,
            street_name=official_street or None,
            house_number=(house_number + (("/" + exponent) if exponent else "")) if house_number else None,
            postal_code=None,
            locality=item.city,
            admin_unit_l2=None,
            admin_unit_l1=item.region_name,
            country_name="Italia",
            country_code="IT",
            latitude=latitude,
            longitude=longitude,
            precision_code=precision,
            attribution=ANNCSU_ATTRIBUTION,
            licence=ANNCSU_LICENCE,
            payload=payload,
        )
        resolved[item.source_address] = AnncsuResolution(item.source_address, status, candidate, item.municipality_code, item.cadastral_code, payload)

    return [resolved[address] for address in source_addresses]
