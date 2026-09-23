"""Register a reviewed repository SourceSeries before relational capture persistence.

This is metadata registration, not acquisition or document identity. The reviewed
source-series inventory identifies a recurring logical series; its URL remains a
locator and is deliberately not persisted as SourceEdition or ContentObject identity.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from white_list_archive.persistence.capture_manifest import (
    RegistryContext,
    _read_csv_index,
    ensure_authority,
    ensure_register,
    ensure_series,
    load_context,
)


@dataclass(frozen=True)
class RegisteredSourceSeries:
    authority_id: str
    register_id: str
    series_id: str
    source_key: str


def _context_for_source_key(
    source_key: str,
    *,
    authority_csv: Path,
    series_csv: Path,
) -> RegistryContext:
    if not isinstance(source_key, str) or not source_key.strip():
        raise ValueError("source_key must be a non-blank reviewed SourceSeries key")
    series = _read_csv_index(series_csv, "source_series_key")
    row = series.get(source_key)
    if row is None:
        raise ValueError(
            f"SourceSeries {source_key!r} is not present in the reviewed source-series inventory"
        )
    authority_key = row.get("authority_key")
    if not authority_key:
        raise ValueError(f"SourceSeries {source_key!r} has no reviewed authority binding")
    return load_context(
        {"authority_key": authority_key, "source_series_key": source_key},
        authority_csv,
        series_csv,
    )


def _verify_authority(cur, authority_id, context: RegistryContext) -> None:
    cur.execute(
        """
        SELECT authority_code, authority_type_code
        FROM core.public_authority WHERE public_authority_id=%s
        """,
        (authority_id,),
    )
    row = cur.fetchone()
    expected = (context.authority_key, context.authority_type_code)
    if row is None or tuple(row) != expected:
        raise ValueError("Existing authority metadata conflicts with reviewed SourceSeries registry")


def _verify_register(cur, register_id, authority_id, context: RegistryContext) -> None:
    cur.execute(
        """
        SELECT r.public_authority_id, g.regime_code
        FROM whitelist.white_list_register r
        JOIN whitelist.white_list_regime g ON g.regime_id=r.regime_id
        WHERE r.register_id=%s
        """,
        (register_id,),
    )
    row = cur.fetchone()
    expected = (authority_id, context.regime_code)
    if row is None or tuple(row) != expected:
        raise ValueError("Existing register metadata conflicts with reviewed SourceSeries registry")


def _verify_series(cur, series_id, authority_id, register_id, context: RegistryContext) -> None:
    cur.execute(
        """
        SELECT series_code, publisher_authority_id, register_id, series_type_code
        FROM source.source_series WHERE series_id=%s
        """,
        (series_id,),
    )
    row = cur.fetchone()
    expected = (context.source_series_key, authority_id, register_id, "list")
    if row is None or tuple(row) != expected:
        raise ValueError("Existing SourceSeries metadata conflicts with reviewed registry")


def ensure_registered_source_series(
    conn,
    *,
    source_key: str,
    authority_csv: Path,
    series_csv: Path,
) -> RegisteredSourceSeries:
    """Idempotently register one repository-reviewed logical SourceSeries.

    The caller owns the transaction. No source URL, capture, bytes, edition label,
    reference date, publication date or effective/legal time is inferred here.
    Existing rows are accepted only when their structural authority/register/series
    bindings agree with the reviewed inventories.
    """
    context = _context_for_source_key(
        source_key,
        authority_csv=authority_csv,
        series_csv=series_csv,
    )
    with conn.cursor() as cur:
        authority_id = ensure_authority(cur, context)
        _verify_authority(cur, authority_id, context)
        register_id = ensure_register(cur, authority_id, context)
        _verify_register(cur, register_id, authority_id, context)
        series_id = ensure_series(cur, authority_id, register_id, context)
        _verify_series(cur, series_id, authority_id, register_id, context)
    return RegisteredSourceSeries(
        authority_id=str(authority_id),
        register_id=str(register_id),
        series_id=str(series_id),
        source_key=context.source_series_key,
    )
