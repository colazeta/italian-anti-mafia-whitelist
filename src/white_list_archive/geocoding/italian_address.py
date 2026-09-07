from __future__ import annotations

import csv
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

TOKEN_RE = re.compile(r"[^\W_]+", re.UNICODE)
PROVINCE_MARKER_RE = re.compile(r"^\s*\(\s*([A-Za-z]{2})\s*\)\s*,?\s*")


def _fold_token(value: str) -> str:
    text = unicodedata.normalize("NFKD", value)
    text = "".join(char for char in text if not unicodedata.combining(char))
    return text.casefold()


def _token_spans(value: str) -> list[tuple[str, int, int]]:
    return [(_fold_token(match.group(0)), match.start(), match.end()) for match in TOKEN_RE.finditer(value)]


@dataclass(frozen=True)
class MunicipalityRecord:
    municipality_code: str
    municipality_name: str
    municipality_name_it: str
    province_plate: str
    region_name: str
    cadastral_code: str

    @property
    def display_name(self) -> str:
        return (self.municipality_name_it or self.municipality_name).strip()


@dataclass(frozen=True)
class ItalianAddressSplit:
    source_address: str
    municipality: MunicipalityRecord
    remainder: str


@dataclass(frozen=True)
class SplitResult:
    status: str
    split: ItalianAddressSplit | None = None
    detail: str | None = None


class MunicipalityPrefixMatcher:
    """Match only an exact official Istat municipality prefix.

    Case, diacritics and punctuation are folded at token boundaries. No fuzzy
    matching, edit distance or inferred aliases are used. The source address is
    never rewritten; the returned remainder exists only for downstream derived
    enrichment.
    """

    def __init__(self, records: Iterable[MunicipalityRecord]) -> None:
        alias_map: dict[tuple[str, ...], dict[str, MunicipalityRecord]] = {}
        for record in records:
            for alias in (record.municipality_name_it, record.municipality_name):
                alias = (alias or "").strip()
                if not alias:
                    continue
                tokens = tuple(token for token, _, _ in _token_spans(alias))
                if tokens:
                    alias_map.setdefault(tokens, {})[record.municipality_code] = record
        self._aliases = alias_map
        self._lengths = sorted({len(tokens) for tokens in alias_map}, reverse=True)

    @classmethod
    def from_istat_csv(cls, path: Path) -> "MunicipalityPrefixMatcher":
        records: list[MunicipalityRecord] = []
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            required = {
                "municipality_code",
                "municipality_name",
                "municipality_name_it",
                "province_plate",
                "region_name",
                "cadastral_code",
            }
            missing = required - set(reader.fieldnames or ())
            if missing:
                raise ValueError(f"Istat crosswalk missing required fields: {sorted(missing)}")
            for row in reader:
                records.append(
                    MunicipalityRecord(
                        municipality_code=(row.get("municipality_code") or "").strip(),
                        municipality_name=(row.get("municipality_name") or "").strip(),
                        municipality_name_it=(row.get("municipality_name_it") or "").strip(),
                        province_plate=(row.get("province_plate") or "").strip().upper(),
                        region_name=(row.get("region_name") or "").strip(),
                        cadastral_code=(row.get("cadastral_code") or "").strip().upper(),
                    )
                )
        return cls(records)

    def split(self, source_address: str) -> SplitResult:
        source_address = (source_address or "").strip()
        if not source_address:
            return SplitResult("blank")
        source_tokens = _token_spans(source_address)
        if not source_tokens:
            return SplitResult("no_tokens")
        folded = tuple(token for token, _, _ in source_tokens)

        matched_records: dict[str, MunicipalityRecord] | None = None
        matched_length = 0
        for length in self._lengths:
            if len(folded) < length:
                continue
            candidates = self._aliases.get(folded[:length])
            if candidates:
                matched_records = candidates
                matched_length = length
                break
        if not matched_records:
            return SplitResult("no_exact_municipality_prefix")
        if len(matched_records) != 1:
            return SplitResult(
                "ambiguous_municipality_prefix",
                detail=",".join(sorted(matched_records)),
            )

        municipality = next(iter(matched_records.values()))
        consumed_end = source_tokens[matched_length - 1][2]
        remainder = source_address[consumed_end:]
        province_match = PROVINCE_MARKER_RE.match(remainder)
        if province_match:
            observed_plate = province_match.group(1).upper()
            if municipality.province_plate and observed_plate != municipality.province_plate:
                return SplitResult(
                    "province_marker_mismatch",
                    detail=f"source={observed_plate};istat={municipality.province_plate}",
                )
            remainder = remainder[province_match.end():]
        remainder = remainder.lstrip(" ,;-\t")
        if not remainder:
            return SplitResult("missing_street_after_municipality")
        return SplitResult(
            "exact",
            ItalianAddressSplit(
                source_address=source_address,
                municipality=municipality,
                remainder=remainder,
            ),
        )
