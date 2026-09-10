from __future__ import annotations

import argparse
import csv
import json
import tempfile
from pathlib import Path

from white_list_archive.publishing.public_national_registry import (
    build_prefecture_index,
    build_registry,
    write_prefecture_csv,
    write_registry_csv,
)


def _read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_rows(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _alias_inputs(
    verified_pages: Path,
    source_series: Path,
    aliases: Path,
    work_dir: Path,
) -> tuple[Path, Path]:
    alias_rows = _read_rows(aliases)
    verified = _read_rows(verified_pages)
    series = _read_rows(source_series)

    for alias in alias_rows:
        national_key = alias["national_index_key"]
        catalog_key = alias["catalog_authority_key"]

        matches = [row for row in verified if row["authority_key"] == catalog_key]
        if len(matches) != 1:
            raise RuntimeError(
                f"Authority alias {national_key}->{catalog_key}: expected exactly one verified primary page, got {len(matches)}"
            )
        alias_verified = dict(matches[0])
        alias_verified["authority_key"] = national_key
        if not any(row["authority_key"] == national_key for row in verified):
            verified.append(alias_verified)

        series_matches = [row for row in series if row["authority_key"] == catalog_key]
        if not series_matches:
            raise RuntimeError(
                f"Authority alias {national_key}->{catalog_key}: no source-series rows found"
            )
        if not any(row["authority_key"] == national_key for row in series):
            for source_row in series_matches:
                alias_series = dict(source_row)
                alias_series["authority_key"] = national_key
                series.append(alias_series)

    work_dir.mkdir(parents=True, exist_ok=True)
    verified_out = work_dir / "verified_primary_pages_with_aliases.csv"
    series_out = work_dir / "source_series_with_aliases.csv"
    _write_rows(verified_out, verified, list(verified[0]))
    _write_rows(series_out, series, list(series[0]))
    return verified_out, series_out


def _alias_publication_config(config: dict, aliases: Path) -> dict:
    """Add national-index authority-key views for index publication status only.

    The registry itself remains keyed to the canonical project authority.  The
    national index, however, derives authority keys from Ministry URLs, which
    can legitimately differ (for example ``pesaro-urbino`` versus the canonical
    ``pesaro-e-urbino``).  Duplicate source views here let the Prefecture index
    recognise an already-published canonical source without changing registry
    identity or source provenance.
    """
    sources = list(config["sources"])
    for alias in _read_rows(aliases):
        national_key = alias["national_index_key"]
        catalog_key = alias["catalog_authority_key"]
        matches = [source for source in config["sources"] if source["authority_key"] == catalog_key]
        if not matches:
            continue
        if any(source["authority_key"] == national_key for source in sources):
            continue
        for source in matches:
            alias_source = dict(source)
            alias_source["authority_key"] = national_key
            sources.append(alias_source)
    return {**config, "sources": sources}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build public national registry and Prefecture index with explicit source/canonical authority aliases"
    )
    parser.add_argument("--source-config", type=Path, required=True)
    parser.add_argument("--verified-pages", type=Path, required=True)
    parser.add_argument("--source-series", type=Path, required=True)
    parser.add_argument("--authority-aliases", type=Path, required=True)
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--registry-json", type=Path, required=True)
    parser.add_argument("--registry-csv", type=Path, required=True)
    parser.add_argument("--prefectures-json", type=Path, required=True)
    parser.add_argument("--prefectures-csv", type=Path, required=True)
    args = parser.parse_args(argv)

    config = json.loads(args.source_config.read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory(prefix="white-list-public-aliases-") as tmp:
        verified, series = _alias_inputs(
            args.verified_pages,
            args.source_series,
            args.authority_aliases,
            Path(tmp),
        )
        registry = build_registry(config, args.work_dir)
        prefectures = build_prefecture_index(
            _alias_publication_config(config, args.authority_aliases),
            verified,
            series,
        )

    args.registry_json.parent.mkdir(parents=True, exist_ok=True)
    args.registry_json.write_text(
        json.dumps(registry, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    write_registry_csv(registry, args.registry_csv)
    args.prefectures_json.write_text(
        json.dumps(prefectures, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    write_prefecture_csv(prefectures, args.prefectures_csv)

    print(
        json.dumps(
            {
                "registry_records": registry["meta"]["record_count"],
                "authorities_published": registry["meta"]["authority_count"],
                "registers_published": registry["meta"]["register_count"],
                "prefectures_in_national_index": prefectures["meta"]["authority_count"],
                "mapped_prefectures": prefectures["meta"]["mapped_count"],
                "published_prefectures": prefectures["meta"]["published_count"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
