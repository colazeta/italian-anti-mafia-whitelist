from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class ProviderStatus:
    provider_name: str
    endpoint: str
    software_version: str | None
    data_updated: datetime | None
    raw: dict[str, Any]


@dataclass(frozen=True)
class GeocodeCandidate:
    provider_result_id: str | None
    candidate_rank: int
    matched_address: str | None
    street_name: str | None
    house_number: str | None
    postal_code: str | None
    locality: str | None
    admin_unit_l2: str | None
    admin_unit_l1: str | None
    country_name: str | None
    country_code: str | None
    latitude: float | None
    longitude: float | None
    precision_code: str | None
    attribution: str | None
    licence: str | None
    payload: dict[str, Any]

    @property
    def is_address_level(self) -> bool:
        return self.precision_code == "address" and bool(self.house_number)
