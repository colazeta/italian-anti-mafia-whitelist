"""Finite source review for the archived 12 November Biella page, family v2."""
from __future__ import annotations

import hashlib
from pathlib import Path

from white_list_archive.acquisition.release_readiness import (
    biella_complete_physical_rows, explicit_update_date,
)
from white_list_archive.publishing.public_national_registry import _parse_source, _semantic_digest
from white_list_archive.publishing.public_contract import public_record

REFERENCE_DATE = '2026-11-12'
SOURCE_SHA256 = '2f12c48f90ac54c3dc8f7039ede87377b98ed13e1adabfb81d0456f0d889b53a'
SOURCE_BYTES = 204517
PROFILES = {
    'biella-listed': {
        'sector_rows': 240, 'public_records': 132, 'identifier_coverage': 92,
        'raw_identifier_only': 40, 'missing_expiry_dates': 1, 'grouped_sector_repetitions': 108,
        'status_counts': {'listed': 108, 'renewal_update_in_progress': 24},
        'semantic_sha256': '0a8c1c5896b0c4f0c43835750604da751e2b6c68a68a2cd6a2ccd3141b338203',
    },
    'biella-applicants': {
        'sector_rows': 111, 'public_records': 111, 'identifier_coverage': 109,
        'raw_identifier_only': 2, 'missing_application_dates': 1, 'unique_source_identities': 110,
        'status_counts': {'listed': 91, 'pending': 16, 'renewal_update_in_progress': 4},
        'semantic_sha256': 'a8dc75ad3637c747f5b66c85e02915d6dd6b5284b7467c04bd450e8910671640',
    },
}


def qualify(path: Path, cfg: dict, *, checked_at: str):
    key = cfg.get('source_key')
    if key not in PROFILES or cfg.get('authority_key') != 'biella' or cfg.get('reference_date') != REFERENCE_DATE:
        raise ValueError('Unreviewed Biella source selection')
    population = 'listed' if key == 'biella-listed' else 'applicant'
    parser = 'biella_html_' + ('listed' if population == 'listed' else 'applicants')
    url = 'https://prefettura.interno.gov.it/it/prefetture/biella/evidenza/white-list'
    if (cfg.get('parser') != parser or cfg.get('population_scope') != population
            or cfg.get('register_key') != 'biella-ordinary'
            or cfg.get('source_page_url') != url or cfg.get('resource_url') != url
            or cfg.get('approval_mode') != 'raw_sha256' or cfg.get('resources') is not None):
        raise ValueError('Biella authority, population, parser or source binding drift')
    raw = path.read_bytes()
    if len(raw) != SOURCE_BYTES or hashlib.sha256(raw).hexdigest() != SOURCE_SHA256 or cfg.get('sha256') != SOURCE_SHA256:
        raise ValueError('Biella exact original identity mismatch')
    if explicit_update_date(raw, checked_at) != REFERENCE_DATE:
        raise ValueError('Biella explicit source update date mismatch')
    batch = _parse_source(path, cfg)
    profile = PROFILES[key]
    for name, value in profile.items():
        if name != 'semantic_sha256' and batch.diagnostics.get(name) != value:
            raise ValueError('Biella reviewed source denominator drift')
    if batch.diagnostics.get('parser_version') != '2' or batch.diagnostics.get('dropped_date_rows') != 0:
        raise ValueError('Biella parser revision or completeness drift')
    if biella_complete_physical_rows(path, cfg['population_scope']) != profile['sector_rows']:
        raise ValueError('Biella physical row census mismatch')
    if _semantic_digest(batch.records) != profile['semantic_sha256']:
        raise ValueError('Biella full source semantics mismatch')
    for row in batch.records: public_record(row)
    return batch
