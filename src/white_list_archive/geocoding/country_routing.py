from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from dataclasses import dataclass
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

from .italian_address import MunicipalityPrefixMatcher

SOFTWARE_NAME = "white_list_archive.geocoding.country_routing"
SOFTWARE_VERSION = "1"
RULESET = "source-explicit-country-first+istat-exact-italian-prefix+conservative-unresolved"

# The current Cosenza corpus contains one defensibly foreign form:
# `PARIGI (FR)Rue ...`. A parenthetical two-letter token is not sufficient on its
# own because Italian province plates can collide with ISO alpha-2 codes (e.g. FR).
# Foreign source-marker recognition therefore also requires a country-specific
# street-language cue. Unsupported/ambiguous markers remain unresolved.
SOURCE_MARKER_RE = re.compile(
    r"^\s*(?P<place>[^,(]{2,80}?)\s*\(\s*(?P<code>[A-Za-z]{2})\s*\)\s*,?\s*(?P<rest>.+)$"
)
FOREIGN_STREET_HINTS: dict[str, tuple[str, ...]] = {
    "FR": ("rue", "avenue", "boulevard", "chemin", "impasse", "allee", "allée", "quai"),
}
ITALIAN_PREFIX_STATUSES = {
    "exact",
    "missing_street_after_municipality",
    "province_marker_mismatch",
    "ambiguous_municipality_prefix",
}


@dataclass(frozen=True)
class CountryAssessment:
    source_country_code: str | None
    derived_country_code: str | None
    classification_status_code: str
    route_code: str
    derivation_reason: str


def _normalised_leading_token(value: str) -> str:
    match = re.match(r"\s*([^\s,;]+)", value or "")
    return (match.group(1) if match else "").casefold().strip(".:-")


def _validated_foreign_marker(source_address: str) -> tuple[str, str] | None:
    match = SOURCE_MARKER_RE.match(source_address or "")
    if not match:
        return None
    code = match.group("code").upper()
    if code == "IT":
        return None
    hints = FOREIGN_STREET_HINTS.get(code)
    if not hints:
        return None
    token = _normalised_leading_token(match.group("rest"))
    if token not in {item.casefold() for item in hints}:
        return None
    return code, match.group("place").strip()


def assess_source_address(
    source_address: str,
    *,
    municipality_matcher: MunicipalityPrefixMatcher,
    explicit_source_country_code: str | None = None,
) -> CountryAssessment:
    """Classify country/routing without rewriting the source address.

    A dedicated source country field, when one exists, wins. Otherwise an exact
    Istat municipality prefix can derive Italy for routing. Foreign text markers
    are accepted only under an explicit conservative validation rule. Everything
    else remains unresolved rather than inheriting Italy from the publishing
    Prefecture.
    """
    explicit = (explicit_source_country_code or "").strip().upper() or None
    if explicit:
        if explicit == "IT":
            return CountryAssessment(
                source_country_code="IT",
                derived_country_code=None,
                classification_status_code="source_explicit",
                route_code="italian_anncsu",
                derivation_reason="dedicated_source_country_code=IT",
            )
        return CountryAssessment(
            source_country_code=explicit,
            derived_country_code=None,
            classification_status_code="source_explicit",
            route_code="foreign_fallback",
            derivation_reason=f"dedicated_source_country_code={explicit}",
        )

    split = municipality_matcher.split(source_address)
    if split.status in ITALIAN_PREFIX_STATUSES:
        return CountryAssessment(
            source_country_code=None,
            derived_country_code="IT",
            classification_status_code="derived_italian",
            route_code="italian_anncsu",
            derivation_reason=f"istat_municipality_prefix:{split.status}",
        )

    foreign = _validated_foreign_marker(source_address)
    if foreign:
        code, place = foreign
        return CountryAssessment(
            source_country_code=code,
            derived_country_code=None,
            classification_status_code="source_explicit",
            route_code="foreign_fallback",
            derivation_reason=(
                f"source_parenthetical_country_marker={code};"
                f"validated_foreign_street_language;place={place}"
            ),
        )

    return CountryAssessment(
        source_country_code=None,
        derived_country_code=None,
        classification_status_code="unresolved",
        route_code="unresolved_fallback",
        derivation_reason=f"no_defensible_country_assignment:{split.status}",
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_reference(istat_csv: Path, istat_manifest: Path) -> tuple[dict[str, Any], str]:
    manifest = json.loads(istat_manifest.read_text(encoding="utf-8"))
    expected = str(manifest.get("crosswalk_csv", {}).get("sha256") or "")
    observed = _sha256(istat_csv)
    if not expected or observed != expected:
        raise ValueError("Istat municipality CSV does not match its manifest SHA-256")
    version = str(manifest.get("provider_version") or manifest.get("generated_at") or expected[:16])
    return manifest, version


def _config_hash(manifest: dict[str, Any]) -> str:
    payload = {
        "software": SOFTWARE_NAME,
        "software_version": SOFTWARE_VERSION,
        "ruleset": RULESET,
        "istat_provider_version": manifest.get("provider_version"),
        "istat_sha256": manifest.get("crosswalk_csv", {}).get("sha256"),
        "foreign_street_hints": FOREIGN_STREET_HINTS,
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _ensure_activity(cur, config_hash: str):
    now = datetime.now(timezone.utc).replace(microsecond=0)
    cur.execute(
        """
        INSERT INTO provenance.processing_activity(
            activity_type_code,software_name,software_version,
            configuration_hash,started_at,completed_at
        ) VALUES ('normalise',%s,%s,%s,%s,%s)
        RETURNING processing_activity_id
        """,
        (SOFTWARE_NAME, SOFTWARE_VERSION, config_hash, now, now),
    )
    return cur.fetchone()[0]


def assess_address_countries(
    conn,
    *,
    istat_csv: Path,
    istat_manifest: Path,
) -> dict[str, Any]:
    manifest, reference_version = _load_reference(istat_csv, istat_manifest)
    matcher = MunicipalityPrefixMatcher.from_istat_csv(istat_csv)
    config_hash = _config_hash(manifest)
    counts: Counter[str] = Counter()

    with conn.cursor() as cur:
        activity_id = _ensure_activity(cur, config_hash)
        cur.execute(
            "SELECT address_id,full_address,country_code FROM core.address ORDER BY address_id"
        )
        rows = cur.fetchall()
        for address_id, full_address, source_country in rows:
            assessment = assess_source_address(
                str(full_address),
                municipality_matcher=matcher,
                explicit_source_country_code=(str(source_country) if source_country else None),
            )
            counts[assessment.route_code] += 1
            cur.execute(
                """
                SELECT source_country_code,derived_country_code,
                       classification_status_code,route_code,derivation_reason,
                       reference_version
                FROM geo.address_country_assessment
                WHERE address_id=%s AND upper_inf(system_period)
                """,
                (address_id,),
            )
            current = cur.fetchone()
            desired = (
                assessment.source_country_code,
                assessment.derived_country_code,
                assessment.classification_status_code,
                assessment.route_code,
                assessment.derivation_reason,
                reference_version,
            )
            if current == desired:
                continue
            if current:
                cur.execute(
                    """
                    UPDATE geo.address_country_assessment
                    SET system_period=tstzrange(lower(system_period),CURRENT_TIMESTAMP,'[)')
                    WHERE address_id=%s AND upper_inf(system_period)
                    """,
                    (address_id,),
                )
            cur.execute(
                """
                INSERT INTO geo.address_country_assessment(
                    address_id,source_country_code,derived_country_code,
                    classification_status_code,route_code,derivation_reason,
                    reference_scheme,reference_version,processing_activity_id
                ) VALUES (%s,%s,%s,%s,%s,%s,'ISTAT_MUNICIPALITIES',%s,%s)
                """,
                (
                    address_id,
                    assessment.source_country_code,
                    assessment.derived_country_code,
                    assessment.classification_status_code,
                    assessment.route_code,
                    assessment.derivation_reason,
                    reference_version,
                    activity_id,
                ),
            )

    return {
        "addresses": sum(counts.values()),
        "route_counts": dict(sorted(counts.items())),
        "configuration_hash": config_hash,
        "reference_version": reference_version,
        "ruleset": RULESET,
    }


def assess_from_dsn(
    dsn: str,
    *,
    istat_csv: Path,
    istat_manifest: Path,
) -> dict[str, Any]:
    if psycopg is None:
        raise RuntimeError("Install the project with the database extra") from _IMPORT_ERROR
    with psycopg.connect(dsn) as conn:
        result = assess_address_countries(
            conn, istat_csv=istat_csv, istat_manifest=istat_manifest
        )
        conn.commit()
        return result
