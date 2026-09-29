"""Read known robot capture identities into the governed recovery programme.

Git metadata supplies references, never proof of durable storage. The complete
manifest is rehydrated from the immutable catalogue; the normal recovery
materialiser still verifies original bytes and determines recovery status.
"""
from __future__ import annotations

import json
from pathlib import Path
import re
import subprocess

from white_list_archive.acquisition.prefecture_robots import _capture_history
from white_list_archive.storage.capture_catalogue import CaptureCatalogue, capture_record_key
from white_list_archive.storage.catalogue_recovery import load_catalogued_capture

_FIELDS = ('sha256', 'byte_size', 'content_type', 'captured_at', 'reference_date', 'http_status')


def read_robot_history(repository_root: Path, ref: str) -> tuple[list, dict]:
    """Freeze one Git head and read every retained state revision reachable from it."""
    def git(*args):
        return subprocess.check_output(['git', '-C', str(repository_root), *args], text=True).strip()

    head = git('rev-parse', '--verify', '--end-of-options', ref + '^{commit}')
    shallow_file = Path(git('rev-parse', '--git-path', 'shallow'))
    if not shallow_file.is_absolute():
        shallow_file = repository_root / shallow_file
    if shallow_file.exists():
        boundaries = set(shallow_file.read_text().splitlines())
        if boundaries.intersection(git('rev-list', head).splitlines()):
            raise ValueError('Robot-state history is shallow; fetch its complete history')
    revisions = git('rev-list', '--reverse', head, '--', 'state.json').splitlines()
    if not revisions:
        raise ValueError('Robot-state history has no retained state')
    snapshots = [(sha, json.loads(git('show', sha + ':state.json'))) for sha in revisions]
    return snapshots, {'robot_state_sha': head, 'robot_state_revisions': len(revisions)}


def collect_robot_capture_references(snapshots: list, source_authorities: dict) -> tuple[list, dict]:
    """Deduplicate actual capture IDs across history without inferring source bindings."""
    selected = {}
    discovery, unbound = set(), set()
    for revision, state in snapshots:
        if not re.fullmatch(r'[a-f0-9]{40}', revision):
            raise ValueError('Robot-state evidence requires an exact Git revision')
        if state.get('schema_version') != 1 or not isinstance(state.get('robots'), dict):
            raise ValueError('Unsupported robot-state snapshot')
        for authority, report in state['robots'].items():
            if report.get('authority_key') != authority:
                raise ValueError('Robot report authority conflicts with its state key')
            for url, resource in report['resources'].items():
                for capture in _capture_history({'authority_key': authority}, resource):
                    source, cid = capture.get('source_key'), capture.get('capture_id')
                    if not isinstance(cid, str) or not cid:
                        raise ValueError('Robot history lacks a recorded capture identity')
                    if source is None:
                        unbound.add((authority, cid))
                        continue
                    capture_record_key({'source_key': source, 'capture_id': cid})
                    if source == authority + '-robot-discovery':
                        discovery.add((source, cid))
                        continue
                    if source not in source_authorities:
                        unbound.add((authority, cid))
                        continue
                    if source_authorities[source] != authority:
                        raise ValueError('Robot capture conflicts with reviewed SourceSeries ownership')
                    identity = (source, cid)
                    row = selected.setdefault(identity, {
                        'authority_key': authority, 'source_key': source, 'capture_id': cid,
                        'resource_url': url, 'expected': {}, 'evidence_refs': [],
                    })
                    if row['resource_url'] != url:
                        raise ValueError('One capture identity has conflicting resource provenance')
                    for field in _FIELDS:
                        value = capture.get(field)
                        if value is None:
                            continue  # Older reports never established these fields.
                        if field in row['expected'] and row['expected'][field] != value:
                            raise ValueError('One capture identity has conflicting historical metadata')
                        row['expected'][field] = value
                    evidence_ref = f'git:robot-state:{revision}:state.json#{authority}'
                    if evidence_ref not in row['evidence_refs']:
                        row['evidence_refs'].append(evidence_ref)
    rows = [selected[key] for key in sorted(selected)]
    return rows, {
        'reviewed_robot_capture_references': len(rows),
        'reviewed_robot_source_series': len({row['source_key'] for row in rows}),
        'reviewed_robot_authorities': len({row['authority_key'] for row in rows}),
        'discovery_capture_references_excluded': len(discovery),
        'unbound_capture_references_excluded': len(unbound),
    }


def rehydrate_robot_captures(references: list, catalogue: CaptureCatalogue) -> list:
    """Read exact catalogue identities; failures never become a missing verdict."""
    captures = []
    for reference in references:
        try:
            manifest, receipt = load_catalogued_capture(
                catalogue, source_key=reference['source_key'], capture_id=reference['capture_id'],
            )
            if manifest['resource_url'] != reference['resource_url']:
                raise ValueError('Catalogue locator conflicts with historical capture provenance')
            if any(manifest.get(k) != v for k, v in reference['expected'].items()):
                raise ValueError('Catalogue manifest conflicts with historical capture metadata')
        except Exception:
            # A provider exception may contain private coordinates. Stop this proof
            # without silently dropping the identity from the selected denominator.
            raise ValueError(
                'Robot capture not verified: ' + reference['source_key'] + '/' + reference['capture_id']
            ) from None
        captures.append({
            'authority_key': reference['authority_key'], 'capture': manifest, 'catalogue': receipt,
            'recovery_paths': [], 'durable_absence_confirmed': False,
            'operator_evidence_refs': reference['evidence_refs'],
        })
    return captures
