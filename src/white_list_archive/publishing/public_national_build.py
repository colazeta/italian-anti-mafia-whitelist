from __future__ import annotations

import argparse
import csv
import json
import os
import tempfile
from collections import Counter
from pathlib import Path

from white_list_archive.publishing.frozen_release import (
    PUBLIC_PROJECTOR_REVISION,
    build_registry_from_release,
    validate_release_runtime,
)
from white_list_archive.publishing.public_contract import validate_registry
from white_list_archive.publishing.public_history import publish_history
from white_list_archive.publishing.public_snapshot import restore
from white_list_archive.publishing.public_national_registry import (
    build_prefecture_index,
    build_registry,
    _semantic_digest,
    write_prefecture_csv,
    write_registry_csv,
)
from white_list_archive.storage.evidence import EvidenceStore, StoreConfig, client_for

# Existing publication adapter keys deliberately differ from their physical
# parser diagnostic names. Keep the mapping explicit; unrelated identities fail.
DECLARED_PARSER_IDENTITIES = {
    'ferrara-provincial-listed': 'ferrara_ordinary',
    'ferrara-provincial-applicants': 'ferrara_applicants',
    'ferrara-reconstruction-listed': 'ferrara_reconstruction_bundle',
    'pordenone-provincial-listed': 'pordenone_listed_bundle',
    'pordenone-provincial-applicants': 'pordenone_applicants',
}


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

    The registry itself remains keyed to the canonical project authority. The
    national index, however, derives authority keys from Ministry URLs, which
    can legitimately differ (for example ``pesaro-urbino`` versus the canonical
    ``pesaro-e-urbino``). Duplicate source views here let the Prefecture index
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


def _canonicalise_prefecture_authority_keys(prefectures: dict, aliases: Path) -> dict:
    """Return the public directory with project-canonical authority identities."""
    alias_map = {
        row["national_index_key"]: row["catalog_authority_key"]
        for row in _read_rows(aliases)
    }
    rows = []
    seen: set[str] = set()
    for source_row in prefectures["prefectures"]:
        row = dict(source_row)
        row["authority_key"] = alias_map.get(row["authority_key"], row["authority_key"])
        if row["authority_key"] in seen:
            raise RuntimeError(
                f"Authority alias collision in public Prefecture directory: {row['authority_key']}"
            )
        seen.add(row["authority_key"])
        rows.append(row)
    return {**prefectures, "prefectures": rows}


def _restore_declared_parser_revisions(registry: dict, config: dict, work_dir: Path) -> dict:
    """Prevent the legacy generic publication adapter from erasing parser revisions.

    Modern parsers already expose their own ``parser_version`` in diagnostics. The
    legacy registry adapter historically rewrote records to a generic 1/2 value.
    Until that large adapter is decomposed, the serial release builder restores the
    parser-declared revision before history/publication and fails on identity drift.
    Parsers without a declared diagnostics revision keep their established legacy
    value; no revision is guessed.
    """
    source_config = {item["source_key"]: item for item in config["sources"]}
    if len(source_config) != len(config["sources"]):
        raise RuntimeError("Publication config contains duplicate source_key")
    declared: dict[str, str] = {}
    for source_key, cfg in source_config.items():
        path = work_dir / f"{source_key}.diagnostics.json"
        if not path.exists():
            raise RuntimeError(f"{source_key}: parser diagnostics missing after registry build")
        diagnostics = json.loads(path.read_text(encoding="utf-8"))
        diagnostic_identity = DECLARED_PARSER_IDENTITIES.get(cfg['parser'], cfg['parser'])
        if diagnostics.get("parser") not in (None, cfg["parser"], diagnostic_identity):
            raise RuntimeError(f"{source_key}: parser diagnostics identify another parser")
        version = diagnostics.get("parser_version")
        if version is None:
            continue
        if not isinstance(version, (str, int)) or not str(version).strip():
            raise RuntimeError(f"{source_key}: invalid parser_version in diagnostics")
        declared[source_key] = str(version)

    seen: set[str] = set()
    for record in registry["records"]:
        source_key = record["source_key"]
        cfg = source_config.get(source_key)
        if cfg is None:
            raise RuntimeError(f"Registry contains unconfigured source_key: {source_key}")
        if record.get("parser_name") != cfg["parser"]:
            raise RuntimeError(f"{source_key}: public record parser identity drift")
        if source_key in declared:
            record["parser_version"] = declared[source_key]
        seen.add(source_key)
    if seen != set(source_config):
        missing = sorted(set(source_config) - seen)
        raise RuntimeError(f"Configured source produced no public records: {missing!r}")
    validate_registry(registry)
    return registry


def _build_registry_with_network_retries(config: dict, work_dir: Path) -> dict:
    """Legacy live candidate. Transient retries happen per request in _download.

    Never delete already acquired evidence or restart unrelated source downloads.
    Hash, parser, semantic and permanent HTTP failures still stop the candidate.
    """
    return build_registry(config, work_dir)


def _build_registry_from_selected_inputs(
    config: dict,
    work_dir: Path,
    release_manifest_path: Path | None,
    *,
    runtime_code_revision: str | None = None,
    preserved_source_keys: tuple[str, ...] = (),
    public_snapshot_manifest: Path | None = None,
) -> dict:
    """Select live legacy mode or strict archive-backed release replay.

    Archive mode has no source-network fallback. Store configuration/credentials are
    read only when an explicit frozen release is supplied. Missing/corrupt selected
    objects fail closed in ``EvidenceStore.read_verified``. Frozen replay additionally
    refuses to run unless the executing code, projector and parser revisions exactly
    match those pinned by the release.
    """
    if bool(preserved_source_keys) != bool(public_snapshot_manifest):
        raise ValueError("Public source preservation requires both explicit source keys and a reviewed snapshot manifest")
    if preserved_source_keys:
        if release_manifest_path is not None:
            raise ValueError("Public derivative preservation cannot be mixed with original-source frozen replay")
        return _build_with_preserved_public_sources(config, work_dir, preserved_source_keys, public_snapshot_manifest)
    release_manifest = None
    if release_manifest_path is None:
        registry = _build_registry_with_network_retries(config, work_dir)
    else:
        if not runtime_code_revision:
            raise ValueError("Frozen release replay requires an explicit runtime code revision")
        release_manifest = json.loads(release_manifest_path.read_text(encoding="utf-8"))
        store_config = StoreConfig.from_env()
        store = EvidenceStore(client_for(store_config), store_config)
        registry = build_registry_from_release(config, work_dir, release_manifest, store)
    registry = _restore_declared_parser_revisions(registry, config, work_dir)
    if release_manifest is not None:
        validate_release_runtime(
            release_manifest,
            registry,
            runtime_code_revision=runtime_code_revision,
            projector_revision=PUBLIC_PROJECTOR_REVISION,
        )
    return registry


def _build_with_preserved_public_sources(config: dict, work_dir: Path, keys: tuple[str, ...], manifest_path: Path) -> dict:
    """Compose explicit approved public editions with newly checked source scopes.

    This is selected before acquisition, never as an automatic error fallback. It
    reuses public projections, not original evidence or a new source verification.
    Old reference/check times, parser revisions and record bytes remain unchanged.
    """
    by_key = {source['source_key']: source for source in config['sources']}
    if len(by_key) != len(config['sources']) or len(set(keys)) != len(keys) or set(keys) - by_key.keys():
        raise ValueError('Unknown or duplicate preserved source selection')
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    with tempfile.TemporaryDirectory(prefix='approved-public-editions-') as temporary:
        restore(manifest, Path(temporary))
        approved = json.loads((Path(temporary) / 'registry.json').read_text(encoding='utf-8'))
    validate_registry(approved)
    preserved_records, preserved_reports = [], []
    for key in keys:
        cfg = by_key[key]
        approval_mode = cfg.get('approval_mode', 'raw_sha256')
        if approval_mode not in {'raw_sha256', 'semantic_sha256'} or cfg.get('resources'):
            raise ValueError(f'{key}: public preservation requires one resource and a supported approval mode')
        reports = [s for s in approved['meta']['sources'] if s['source_key'] == key]
        if len(reports) != 1:
            raise ValueError(f'{key}: approved public edition is absent or ambiguous')
        report = reports[0]
        identity_fields = ('source_key', 'authority_key', 'register_key', 'population_scope', 'reference_date', 'parser')
        if approval_mode == 'raw_sha256':
            identity_fields += ('sha256',)
        for field in identity_fields:
            if report.get(field) != cfg.get(field):
                raise ValueError(f'{key}: preserved edition differs from configured {field}')
        if not report.get('document_checked_at'):
            raise ValueError(f'{key}: preserved edition has no original verification time')
        records = [r for r in approved['records'] if r['source_key'] == key]
        if not records or (cfg.get('expected_source_rows') is not None and len(records) != cfg['expected_source_rows']):
            raise ValueError(f'{key}: preserved observation count differs from reviewed configuration')
        if approval_mode == 'semantic_sha256' and _semantic_digest(records) != cfg.get('semantic_sha256'):
            # Preserve only a projection that independently recomputes to the
            # configured approved semantics. Its actual original raw digest stays
            # bound to the verified snapshot and records, never to today's URL.
            raise ValueError(f'{key}: preserved observations differ from approved semantic digest')
        for record in records:
            for field in ('authority_key', 'register_key', 'population_scope', 'reference_date', 'source_page_url', 'resource_url'):
                if record.get(field) != cfg.get(field):
                    raise ValueError(f'{key}: preserved observation differs from configured {field}')
            if record.get('parser_name') != cfg['parser'] or not record.get('parser_version'):
                raise ValueError(f'{key}: preserved parser provenance is missing or different')
        preserved_records.extend(records)
        preserved_reports.append(report)
    fresh_config = {**config, 'sources': [s for s in config['sources'] if s['source_key'] not in keys]}
    registry = _build_registry_from_selected_inputs(fresh_config, work_dir, None)
    registry['records'].extend(preserved_records)
    registry['meta']['sources'].extend(preserved_reports)
    meta = registry['meta']
    meta['record_count'] = len(registry['records'])
    meta['source_count'] = len(meta['sources'])
    for dimension in ('authority', 'register', 'status'):
        field = 'source_status' if dimension == 'status' else f'{dimension}_key'
        counts = dict(Counter(r[field] for r in registry['records']))
        meta[f'{dimension}_counts'] = counts
        if dimension != 'status':
            meta[f'{dimension}_count'] = len(counts)
    validate_registry(registry)
    print('Preserved approved public editions (original verification dates unchanged): ' + ', '.join(keys))
    return registry


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
    parser.add_argument('--preserve-public-source', action='append', default=[],
                        help='Explicitly reuse an unchanged approved public source edition; repeat for each scope.')
    parser.add_argument('--preserved-public-sources', type=Path,
                        help='Reviewed JSON list of explicit source keys to preserve from the public snapshot.')
    parser.add_argument('--public-snapshot-manifest', type=Path,
                        help='Hash-pinned public derivative manifest required for explicit public source preservation.')
    parser.add_argument(
        "--release-manifest",
        type=Path,
        help="Frozen archive-backed release manifest. When supplied, source payloads are never fetched live.",
    )
    parser.add_argument(
        "--runtime-code-revision",
        default=os.environ.get("GITHUB_SHA"),
        help="Exact executing code revision. Required for frozen replay; defaults to GITHUB_SHA in Actions.",
    )
    args = parser.parse_args(argv)
    preserved_keys = args.preserve_public_source
    if args.preserved_public_sources:
        selected = json.loads(args.preserved_public_sources.read_text(encoding='utf-8'))
        if not isinstance(selected, list) or any(not isinstance(key, str) for key in selected):
            parser.error('--preserved-public-sources requires a JSON list of source-key strings')
        preserved_keys = [*preserved_keys, *selected]
    if args.release_manifest and not args.runtime_code_revision:
        parser.error("--runtime-code-revision is required for frozen release replay outside GitHub Actions")

    config = json.loads(args.source_config.read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory(prefix="white-list-public-aliases-") as tmp:
        verified, series = _alias_inputs(
            args.verified_pages,
            args.source_series,
            args.authority_aliases,
            Path(tmp),
        )
        registry = _build_registry_from_selected_inputs(
            config,
            args.work_dir,
            args.release_manifest,
            runtime_code_revision=args.runtime_code_revision,
            preserved_source_keys=tuple(preserved_keys),
            public_snapshot_manifest=args.public_snapshot_manifest,
        )
        prefectures = build_prefecture_index(
            _alias_publication_config(config, args.authority_aliases),
            verified,
            series,
        )
        prefectures = _canonicalise_prefecture_authority_keys(
            prefectures,
            args.authority_aliases,
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
    publish_history(
        registry,
        Path(__file__).resolve().parents[3],
        args.registry_json.with_name("history.json"),
    )

    print(
        json.dumps(
            {
                "registry_records": registry["meta"]["record_count"],
                "authorities_published": registry["meta"]["authority_count"],
                "registers_published": registry["meta"]["register_count"],
                "prefectures_in_national_index": prefectures["meta"]["authority_count"],
                "mapped_prefectures": prefectures["meta"]["mapped_count"],
                "published_prefectures": prefectures["meta"]["published_count"],
                "source_mode": "archived_frozen_release" if args.release_manifest else "legacy_live_migration_mode",
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
