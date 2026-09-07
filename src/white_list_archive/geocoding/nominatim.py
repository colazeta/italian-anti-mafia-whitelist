from __future__ import annotations

import json
import re
import time
import unicodedata
import urllib.parse
import urllib.request
from datetime import datetime
from typing import Any

from .models import GeocodeCandidate, ProviderStatus

PUBLIC_NOMINATIM_ENDPOINT = "https://nominatim.openstreetmap.org"
DEFAULT_USER_AGENT = (
    "italian-anti-mafia-whitelist/0.1 "
    "(+https://github.com/colazeta/italian-anti-mafia-whitelist)"
)
PROVINCE_OR_COUNTRY_MARKER_RE = re.compile(r"\s*\(\s*[A-Za-z]{2}\s*\)\s*,?\s*")
ITALIAN_STREET_TOKEN_RE = re.compile(
    r"\b(VIALE|VIA|CORSO|PIAZZA|PIAZZALE|LARGO|CONTRADA|C/DA|STRADA|LOCALIT[AÀ])\b",
    re.IGNORECASE,
)


def _clean_endpoint(value: str) -> str:
    return value.strip().rstrip("/")


def lightly_clean_query(value: str) -> str:
    """Make source formatting geocoder-friendly without parsing the address.

    This is deliberately syntactic only: normalise Unicode/whitespace, separate
    glued two-letter markers, and add a comma before a common Italian street
    designator when the source omitted one. The source-supported address is not
    changed and no municipality/country meaning is inferred from the marker.
    """
    text = unicodedata.normalize("NFKC", value or "")
    text = " ".join(text.split()).strip()
    if not text:
        return ""
    text = PROVINCE_OR_COUNTRY_MARKER_RE.sub(", ", text)
    text = re.sub(r"\s*,\s*,+\s*", ", ", text)
    text = re.sub(r"\s*,\s*", ", ", text)
    match = ITALIAN_STREET_TOKEN_RE.search(text)
    if match and "," not in text[: match.start()]:
        text = text[: match.start()].rstrip(" ,") + ", " + text[match.start() :].lstrip()
    return text.strip(" ,")


def query_variants(value: str) -> list[str]:
    raw = " ".join(unicodedata.normalize("NFKC", value or "").split()).strip()
    if not raw:
        return []
    cleaned = lightly_clean_query(raw)
    return [raw] if not cleaned or cleaned == raw else [raw, cleaned]


def _parse_datetime(value: Any) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _first_nonblank(mapping: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = mapping.get(key)
        if value is not None:
            text = str(value).strip()
            if text:
                return text
    return None


def _precision_from_geocode_type(value: str | None) -> str:
    value = (value or "").strip().lower()
    if value in {"house", "building", "address"}:
        return "address"
    if value in {"street", "road"}:
        return "street"
    if value in {"postcode", "postal_code"}:
        return "postal_code"
    if value in {"city", "town", "village", "hamlet", "locality"}:
        return "locality"
    if value in {"county", "state", "district", "region", "country"}:
        return "admin"
    return "unknown"


def parse_geocodejson(payload: dict[str, Any]) -> list[GeocodeCandidate]:
    features = payload.get("features")
    if not isinstance(features, list):
        raise ValueError("Nominatim geocodejson response has no features array")

    root_meta = payload.get("geocoding")
    if not isinstance(root_meta, dict):
        root_meta = {}
    attribution = _first_nonblank(root_meta, "attribution")
    licence = _first_nonblank(root_meta, "licence", "license")

    output: list[GeocodeCandidate] = []
    for rank, feature in enumerate(features, start=1):
        if not isinstance(feature, dict):
            continue
        properties = feature.get("properties")
        if not isinstance(properties, dict):
            properties = {}
        geocoding = properties.get("geocoding")
        if not isinstance(geocoding, dict):
            geocoding = {}
        geometry = feature.get("geometry")
        if not isinstance(geometry, dict):
            geometry = {}
        coordinates = geometry.get("coordinates")
        longitude = latitude = None
        if isinstance(coordinates, list) and len(coordinates) >= 2:
            try:
                longitude = float(coordinates[0])
                latitude = float(coordinates[1])
            except (TypeError, ValueError):
                longitude = latitude = None

        osm_type = _first_nonblank(geocoding, "osm_type") or _first_nonblank(properties, "osm_type")
        osm_id = _first_nonblank(geocoding, "osm_id") or _first_nonblank(properties, "osm_id")
        provider_result_id = f"osm:{osm_type}:{osm_id}" if osm_type and osm_id else None

        country_code = _first_nonblank(
            geocoding,
            "country_code",
            "countrycode",
            "country_iso_code",
        )
        if country_code:
            country_code = country_code.upper()

        geocode_type = _first_nonblank(geocoding, "type", "addresstype")
        precision_code = _precision_from_geocode_type(geocode_type)
        name = _first_nonblank(geocoding, "name")
        street_name = _first_nonblank(geocoding, "street", "road")
        locality = _first_nonblank(
            geocoding,
            "city",
            "town",
            "village",
            "locality",
            "municipality",
        )
        if not street_name and precision_code == "street":
            street_name = name
        if not locality and precision_code == "locality":
            locality = name

        output.append(
            GeocodeCandidate(
                provider_result_id=provider_result_id,
                candidate_rank=rank,
                matched_address=_first_nonblank(geocoding, "label", "display_name"),
                street_name=street_name,
                house_number=_first_nonblank(geocoding, "housenumber", "house_number"),
                postal_code=_first_nonblank(geocoding, "postcode", "postal_code"),
                locality=locality,
                admin_unit_l2=_first_nonblank(geocoding, "county", "district"),
                admin_unit_l1=_first_nonblank(geocoding, "state", "region"),
                country_name=_first_nonblank(geocoding, "country"),
                country_code=country_code,
                latitude=latitude,
                longitude=longitude,
                precision_code=precision_code,
                attribution=attribution,
                licence=licence,
                payload=feature,
            )
        )
    return output


class NominatimClient:
    """Small Nominatim-compatible client with explicit public-service opt-in."""

    provider_name = "nominatim"

    def __init__(
        self,
        endpoint: str,
        *,
        allow_public_service: bool = False,
        user_agent: str = DEFAULT_USER_AGENT,
        min_interval_seconds: float = 0.0,
        timeout_seconds: float = 30.0,
    ) -> None:
        self.endpoint = _clean_endpoint(endpoint)
        if not self.endpoint:
            raise ValueError("Nominatim endpoint must not be blank")
        self.is_public_osmf_service = self.endpoint == PUBLIC_NOMINATIM_ENDPOINT
        if self.is_public_osmf_service and not allow_public_service:
            raise ValueError(
                "Use of nominatim.openstreetmap.org requires explicit "
                "allow_public_service=True and compliance with the OSMF Nominatim usage policy"
            )
        self.user_agent = user_agent.strip()
        if not self.user_agent:
            raise ValueError("A descriptive User-Agent is required")
        if self.is_public_osmf_service and min_interval_seconds < 1.0:
            min_interval_seconds = 1.05
        self.min_interval_seconds = max(0.0, float(min_interval_seconds))
        self.timeout_seconds = float(timeout_seconds)
        self._last_request_monotonic: float | None = None

    def _throttle(self) -> None:
        if self._last_request_monotonic is None or self.min_interval_seconds <= 0:
            return
        elapsed = time.monotonic() - self._last_request_monotonic
        remaining = self.min_interval_seconds - elapsed
        if remaining > 0:
            time.sleep(remaining)

    def _request_json(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        self._throttle()
        url = self.endpoint + path
        if params:
            url += "?" + urllib.parse.urlencode(params)
        request = urllib.request.Request(
            url,
            headers={"User-Agent": self.user_agent, "Accept": "application/json"},
            method="GET",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                raw = response.read()
        finally:
            self._last_request_monotonic = time.monotonic()
        try:
            payload = json.loads(raw.decode("utf-8"))
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"Nominatim returned invalid JSON from {url}") from exc
        if not isinstance(payload, dict):
            raise RuntimeError(f"Nominatim returned a non-object JSON response from {url}")
        return payload

    def status(self) -> ProviderStatus:
        payload = self._request_json("/status", {"format": "json"})
        status_code = payload.get("status")
        if status_code not in (0, "0", None):
            raise RuntimeError(f"Nominatim status failed: {payload}")
        return ProviderStatus(
            provider_name=self.provider_name,
            endpoint=self.endpoint,
            software_version=_first_nonblank(payload, "software_version", "database_version"),
            data_updated=_parse_datetime(payload.get("data_updated")),
            raw=payload,
        )

    def search(
        self,
        query: str,
        *,
        limit: int = 3,
        language: str = "it",
        countrycodes: str | None = None,
    ) -> list[GeocodeCandidate]:
        query = query.strip()
        if not query:
            return []
        if limit < 1 or limit > 40:
            raise ValueError("Nominatim search limit must be between 1 and 40")
        params: dict[str, Any] = {
            "q": query,
            "format": "geocodejson",
            "addressdetails": 1,
            "limit": limit,
            "dedupe": 1,
            "accept-language": language,
        }
        if countrycodes:
            params["countrycodes"] = countrycodes
        return parse_geocodejson(self._request_json("/search", params))
