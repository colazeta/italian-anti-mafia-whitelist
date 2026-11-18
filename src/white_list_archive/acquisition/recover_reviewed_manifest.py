"""Reconstruct and replay a missing private manifest for an exact reviewed scope."""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
import re
from pathlib import Path
import tempfile

from white_list_archive.acquisition.auto_transform import private_connection
from white_list_archive.storage.capture_catalogue import CaptureCatalogue
from white_list_archive.storage.catalogue_recovery import load_catalogued_capture
from white_list_archive.storage.evidence import EvidenceStore, StoreConfig, client_for
from white_list_archive.publishing.frozen_release import PUBLIC_PROJECTOR_REVISION, configuration_sha256
from white_list_archive.publishing.frozen_release_select import _head_revision, select_verified_release, write_new_release
from white_list_archive.publishing.publication_handoff import records_digest
from white_list_archive.publishing.public_national_build import _build_registry_from_selected_inputs


def selection(request, connection, catalogue):
    sources = request['config']['sources']
    keys = [source['source_key'] for source in sources]
    changes = request['changes']
    if not keys or len(set(keys)) != len(keys) or set(keys) != set(changes) or set(keys) != set(request['parser_versions']):
        raise ValueError('Reviewed configuration, parser revisions and changes must cover identical scopes')
    bindings = []
    for source in sources:
        key = source['source_key']
        expected = changes[key]
        if source.get('resources') or any(source[field] != expected[field] for field in ('sha256', 'parser', 'reference_date')):
            raise ValueError(f'{key}: unsupported bundle or inconsistent review')
        # Repeated checks of identical original bytes are equivalent for content.
        # Prefer the latest compatible check, with a deterministic tie-break.
        rows = connection.execute("""
            SELECT c.capture_id FROM source.source_capture c
            JOIN source.source_series s USING (series_id)
            JOIN source.content_object o USING (content_object_id)
            WHERE s.series_code = %s AND o.sha256 = %s
              AND (c.declared_reference_date IS NULL OR c.declared_reference_date = %s)
            ORDER BY c.captured_at DESC, c.capture_id DESC LIMIT 1
        """, (key, expected['sha256'], expected['reference_date'])).fetchall()
        if not rows:
            raise ValueError(f'{key}: no capture matches the reviewed source, original and date')
        capture, receipt = load_catalogued_capture(catalogue, source_key=key, capture_id=str(rows[0][0]))
        if capture['sha256'] != expected['sha256'] or capture['resource_url'] != source['resource_url']:
            raise ValueError(f'{key}: private catalogue disagrees with the reviewed original')
        bindings.append(dict(source_key=key, parser_revision=f"{source['parser']}@{request['parser_versions'][key]}",
                             projector_revision=PUBLIC_PROJECTOR_REVISION,
                             resources=[dict(label='primary', capture=capture, catalogue=receipt,
                                             reviewed_resource_url=source['resource_url'],
                                             source_reference_date=expected['reference_date'])]))
    return bindings


def retain_manifest(store, manifest):
    body = json.dumps(manifest, ensure_ascii=False, sort_keys=True,
                      separators=(',', ':'), allow_nan=False).encode()
    if len(body) > 2_000_000:
        raise ValueError('Recovered manifest exceeds the private receipt limit')
    digest = hashlib.sha256(body).hexdigest()
    key = f'operations/v1/reviewed-replay/manifests/{digest}.json'
    try:
        store.client.put_object(Bucket=store.config.bucket, Key=key, Body=body,
                                ContentType='application/json', IfNoneMatch='*')
    except Exception as exc:
        if getattr(exc, 'response', {}).get('Error', {}).get('Code') not in {'PreconditionFailed', '412'}:
            raise
    stream = store.client.get_object(Bucket=store.config.bucket, Key=key)['Body']
    try:
        if stream.read(len(body) + 1) != body:
            raise ValueError('Recovered private manifest failed exact readback')
    finally:
        stream.close()
    return digest


def read_private(store, key, limit):
    stream = store.client.get_object(Bucket=store.config.bucket, Key=key)['Body']
    try:
        body = stream.read(limit + 1)
        if len(body) > limit:
            raise ValueError('Private recovery object exceeds limit')
        return body
    finally:
        stream.close()


def indexed_manifest(store, key, directory):
    digest = read_private(store, key, 64).decode('ascii')
    if not re.fullmatch('[0-9a-f]{64}', digest):
        raise ValueError('Invalid private replay index')
    body = read_private(store, f'operations/v1/reviewed-replay/manifests/{digest}.json', 2_000_000)
    if hashlib.sha256(body).hexdigest() != digest:
        raise ValueError('Private indexed manifest digest mismatch')
    (directory/'manifest.json').write_bytes(body)
    return digest


def recover(request_path, directory, connection, store):
    request = json.loads(request_path.read_text())
    config = request['config']
    bindings = selection(request, connection, CaptureCatalogue(store))
    revision = _head_revision()
    identity = configuration_sha256([request_path.stem, request, bindings, revision])
    index = f'operations/v1/reviewed-replay/index/{identity}'
    receipt = {'request': request_path.stem, 'sources_verified': len(bindings),
               'records_verified': sum(change['count'] for change in request['changes'].values()),
               'code_revision': revision}
    try:
        store.client.head_object(Bucket=store.config.bucket, Key=index)
    except Exception as exc:
        if getattr(exc, 'response', {}).get('Error', {}).get('Code') not in {'404', 'NotFound', 'NoSuchKey'}:
            raise
    else:
        return {**receipt, 'private_manifest_sha256': indexed_manifest(store, index, directory)}
    manifest = select_verified_release(
        config, dict(schema_version=2, release_id=request_path.stem, sources=bindings),
        store, code_revision=revision, created_at=datetime.now(timezone.utc).isoformat())
    path = directory / 'manifest.json'
    write_new_release(path, manifest)
    registry = _build_registry_from_selected_inputs(config, directory, path, runtime_code_revision=revision)
    for key, expected in request['changes'].items():
        rows = [row for row in registry['records'] if row['source_key'] == key]
        if (len(rows) != expected['count'] or Counter(row['source_status'] for row in rows) != expected['statuses']
                or records_digest(rows) != expected['records_sha256']):
            raise ValueError(f'{key}: frozen replay differs from the independently reviewed public records')
    digest = retain_manifest(store, manifest)
    try:
        store.client.put_object(Bucket=store.config.bucket, Key=index, Body=digest.encode(), IfNoneMatch='*')
    except Exception as exc:
        if getattr(exc, 'response', {}).get('Error', {}).get('Code') not in {'PreconditionFailed', '412'}:
            raise
    return {**receipt, 'private_manifest_sha256': indexed_manifest(store, index, directory)}


def main():
    config = StoreConfig.from_env()
    store = EvidenceStore(client_for(config), config)
    failures = []
    with private_connection(os.environ['EVIDENCE_DATABASE_URL']) as connection:
        connection.autocommit = True
        for request in sorted(Path('data/publication/archive_replay_requests').glob('*.json')):
            try:
                with tempfile.TemporaryDirectory() as directory:
                    print(json.dumps(recover(request, Path(directory), connection, store)), flush=True)
            except Exception as exc:
                failures.append(request.stem)
                print(f'{request.stem}: recovery blocked ({type(exc).__name__})', flush=True)
    if failures:
        raise SystemExit('Blocked replay requests: ' + ', '.join(failures))


if __name__ == '__main__':
    main()
