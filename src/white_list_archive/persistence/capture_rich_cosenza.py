"""Append rich Cosenza source records to an existing durable capture, without editions."""
from __future__ import annotations

from datetime import datetime
import hashlib
import json
import re
from uuid import UUID

from white_list_archive.acquisition.auto_transform import read_snapshot_verified
from white_list_archive.parsers import cosenza_combined_v2 as parser
from white_list_archive.parsers.registry import select_parser
from white_list_archive.persistence.parse_snapshot import persist_parse_snapshot, snapshot_sha256
from white_list_archive.persistence.parsed_records import (
    _ensure_entity_mention, _ensure_field_definition, _ensure_field_value, _ensure_parsed_record,
)
from white_list_archive.persistence.parsed_records_v2 import (
    FIELD_DEFINITIONS, REQUIRED_RECORD_COLUMNS, _parsed_value,
)

SOURCE_KEY = 'cosenza-combined'
READ_TABLES = (
    'source.source_capture', 'source.content_object', 'source.source_series',
    'source.source_schema', 'source.source_schema_version', 'source.source_field_definition',
    'source.parse_run', 'source.parse_run_input', 'source.capture_parse_run',
    'source.parse_snapshot', 'source.parsed_record', 'source.source_field_value',
    'source.entity_mention', 'provenance.processing_activity',
)
INSERT_TABLES = tuple(t for t in READ_TABLES if t not in (
    'source.source_capture', 'source.content_object', 'source.source_series',
))


class MissingSourcePrivileges(PermissionError):
    def __init__(self, missing):
        self.missing = missing
        super().__init__('Capture-only source persistence privileges are unavailable')


def missing_privileges(conn):
    """Fixed implementation-derived SQL requirements; no GRANT or role mutation."""
    requirements = [(t, 'SELECT') for t in READ_TABLES] + [(t, 'INSERT') for t in INSERT_TABLES]
    with conn.cursor() as cur:
        cur.execute('SELECT t,p,has_table_privilege(current_user,t,p) FROM '
                    'unnest(%s::text[],%s::text[]) AS required(t,p)',
                    ([t for t, _ in requirements], [p for _, p in requirements]))
        return [{'table': t, 'privilege': p} for t, p, available in cur.fetchall() if not available]


def validate_records(records, expected_count):
    if type(expected_count) is not int or not 0 < expected_count <= 10000:
        raise ValueError('A bounded positive source-record denominator is required')
    if not isinstance(records, list) or len(records) != expected_count:
        raise ValueError('Rich record count differs from the pinned source denominator')
    for ordinal, row in enumerate(records, 1):
        if not isinstance(row, dict) or set(row) != REQUIRED_RECORD_COLUMNS:
            raise ValueError('Rich record contract differs from the validated parser family')
        if type(row['row_ordinal']) is not int or row['row_ordinal'] != ordinal:
            raise ValueError('Rich record ordinals must be unique, sequential physical row locators')
        if any(not isinstance(value, str) for key, value in row.items() if key != 'row_ordinal'):
            raise ValueError('Rich source values must preserve the parser string contract')
        raw_digest = hashlib.sha256(re.sub(r'\s+', ' ', row['raw_block']).strip().encode()).hexdigest()
        mention = '\x1f'.join([row['identifier_field_raw'].replace('\n', ''),
                              parser.normalise_name(row['operator_name_raw'])])
        if (row['record_hash'] != raw_digest or
            row['mention_key'] != hashlib.sha256(mention.encode()).hexdigest() or
            row['operator_name_normalised'] != parser.normalise_name(row['operator_name_raw'])):
            raise ValueError('Rich record hash/name/mention integrity failed')
        for key in ('identifiers_json', 'requested_activities_json', 'application_dates_json'):
            if not isinstance(json.loads(row[key]), list):
                raise ValueError('Rich structured field violates list contract')
        outcome = json.loads(row['outcome_json'])
        if not isinstance(outcome, dict) or outcome.get('status') != row['source_status']:
            raise ValueError('Rich source outcome/status contract differs')
    # Complete canonical serialisability is checked before any writes.
    return snapshot_sha256(records, _diagnostics(expected_count))


def _diagnostics(count):
    return {'record_contract': 'prefecture-combined-whitelist-v1',
            'schema_fingerprint': parser.SCHEMA_FINGERPRINT, 'source_rows': count,
            'capture_only': True, 'edition_attribution_created': False}


def _capture_context(cur, capture_id, source_sha256):
    cur.execute('''SELECT s.series_id,o.content_object_id,o.sha256,o.storage_status_code
        FROM source.source_capture c
        JOIN source.source_series s ON s.series_id=c.series_id
        JOIN source.content_object o ON o.content_object_id=c.content_object_id
        WHERE c.capture_id=%s AND s.series_code=%s''', (capture_id, SOURCE_KEY))
    row = cur.fetchone()
    if not row or row[2:] != (source_sha256, 'durable'):
        raise ValueError('Rich source input is not the selected existing durable capture')
    return row[0], row[1]


def _schema(cur, series_id, observed_at):
    # Serialize schema metadata too, across distinct historical captures/revisions.
    cur.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',
                (SOURCE_KEY + ':' + parser.SCHEMA_FINGERPRINT,))
    cur.execute('''SELECT sv.schema_version_id FROM source.source_schema ss
        JOIN source.source_schema_version sv ON sv.source_schema_id=ss.source_schema_id
        WHERE ss.series_id=%s AND sv.structural_fingerprint=%s''',
        (series_id, parser.SCHEMA_FINGERPRINT))
    existing = cur.fetchall()
    if len(existing) > 1:
        raise ValueError('Reviewed source fingerprint has ambiguous schema registration')
    if existing:
        return existing[0][0]
    cur.execute('''SELECT source_schema_id FROM source.source_schema
        WHERE series_id=%s AND schema_name=%s''',
        (series_id, 'Cosenza combined White List PDF layout'))
    rows = cur.fetchall()
    if len(rows) > 1:
        raise ValueError('Rich source schema registration is ambiguous')
    if rows:
        schema_id = rows[0][0]
    else:
        cur.execute('''INSERT INTO source.source_schema(series_id,schema_name)
            VALUES (%s,%s) RETURNING source_schema_id''',
            (series_id, 'Cosenza combined White List PDF layout'))
        schema_id = cur.fetchone()[0]
    cur.execute('''INSERT INTO source.source_schema_version(
        source_schema_id,structural_fingerprint,first_observed_at)
        VALUES (%s,%s,%s) RETURNING schema_version_id''',
        (schema_id, parser.SCHEMA_FINGERPRINT, observed_at))
    return cur.fetchone()[0]


def verify_rich_readback(conn, *, capture_id, parse_run_id, source_sha256,
                         expected_count, expected_snapshot_sha256, code_revision):
    """Rehash full persisted snapshot and compare every rich field and locator."""
    records, diagnostics = read_snapshot_verified(conn, parse_run_id)
    digest = validate_records(records, expected_count)
    if diagnostics != _diagnostics(expected_count) or digest != expected_snapshot_sha256:
        raise ValueError('Rich snapshot readback differs from the pinned interpretation')
    with conn.cursor() as cur:
        _capture_context(cur, capture_id, source_sha256)
        cur.execute('''SELECT cpr.input_label,i.content_object_id=cap.content_object_id,
            pr.status_code,pa.software_name,pa.software_version,pa.configuration_hash
            FROM source.capture_parse_run cpr
            JOIN source.parse_run_input i ON i.parse_run_id=cpr.parse_run_id AND i.input_label=cpr.input_label
            JOIN source.source_capture cap ON cap.capture_id=cpr.capture_id
            JOIN source.parse_run pr ON pr.parse_run_id=cpr.parse_run_id
            JOIN provenance.processing_activity pa ON pa.processing_activity_id=pr.processing_activity_id
            WHERE cpr.capture_id=%s AND cpr.parse_run_id=%s
              AND (SELECT count(*) FROM source.parse_run_input pi WHERE pi.parse_run_id=pr.parse_run_id)=1''', (capture_id, parse_run_id))
        inputs = cur.fetchall()
        if (len(inputs) != 1 or inputs[0][:4] != ('primary', True, 'succeeded', parser.PARSER_NAME)
            or inputs[0][4] != f'{parser.PARSER_VERSION}+git.{code_revision}'
            or inputs[0][5] != parser.PARSER_CONFIGURATION_HASH):
            raise ValueError('Rich parse/capture lineage readback failed')
        cur.execute('''SELECT pr.parsed_record_id,pr.record_locator,pr.record_hash,pr.raw_record_text,
                              sv.structural_fingerprint,s.series_code
            FROM source.parsed_record pr JOIN source.source_schema_version sv USING(schema_version_id)
            JOIN source.source_schema ss ON ss.source_schema_id=sv.source_schema_id
            JOIN source.source_series s ON s.series_id=ss.series_id
            WHERE pr.parse_run_id=%s ORDER BY pr.record_locator''', (parse_run_id,))
        parsed = cur.fetchall()
        expected = [(f'row:{r["row_ordinal"]:06d}', r['record_hash'], r['raw_block'],
                     parser.SCHEMA_FINGERPRINT, SOURCE_KEY) for r in records]
        if [tuple(row[1:]) for row in parsed] != expected:
            raise ValueError('Rich parsed records/locators failed complete readback')
        for stored, source in zip(parsed, records):
            cur.execute('''SELECT fd.structural_locator,fd.normalised_source_label,
                fd.ordinal_position,fd.source_label,fd.observed_datatype,fd.observed_cardinality,
                sfv.raw_value,sfv.parsed_value_json,sfv.structural_locator
                FROM source.source_field_value sfv
                JOIN source.source_field_definition fd USING(field_definition_id)
                WHERE sfv.parsed_record_id=%s ORDER BY fd.ordinal_position''', (stored[0],))
            actual = cur.fetchall()
            wanted = [(d['structural_locator'],d['normalised_source_label'],d['ordinal_position'],
                       d['source_label'],d['observed_datatype'],d['observed_cardinality'],
                       source[d['key']],_parsed_value(source,d),d['structural_locator'].split(':',1)[1])
                      for d in FIELD_DEFINITIONS]
            if actual != wanted:
                raise ValueError('Rich field values/definitions failed full readback')
            cur.execute('SELECT mention_role_code FROM source.entity_mention WHERE parsed_record_id=%s',
                        (stored[0],))
            if cur.fetchall() != [('unknown',)]:
                raise ValueError('Rich entity mentions failed complete readback')
    return {'parse_run_id': str(parse_run_id), 'record_count': expected_count,
            'field_value_count': expected_count * len(FIELD_DEFINITIONS),
            'entity_mention_count': expected_count, 'snapshot_sha256': digest,
            'rich_readback_verified': True, 'editions_created': 0, 'publications': 0}


def persist_capture_records(conn, *, capture_id, source_sha256, records,
                            code_revision, started_at, completed_at, expected_count):
    """Caller owns transaction; atomically append source-only interpretation rows."""
    capture_id = str(UUID(str(capture_id)))
    if not isinstance(source_sha256,str) or not re.fullmatch('[0-9a-f]{64}', source_sha256):
        raise ValueError('An exact source SHA-256 is required')
    if not isinstance(code_revision,str) or not re.fullmatch('[0-9a-f]{40}',code_revision):
        raise ValueError('An exact executing Git revision is required')
    if any(not isinstance(t,datetime) or t.tzinfo is None or t.utcoffset() is None
           for t in (started_at,completed_at)) or completed_at < started_at:
        raise ValueError('Parser processing times must be ordered timezone-aware datetimes')
    digest = validate_records(records, expected_count)
    selection = select_parser(SOURCE_KEY, parser.SCHEMA_FINGERPRINT)
    if (selection.family.implementation_module != parser.PARSER_NAME or
            selection.family.parser_version != parser.PARSER_VERSION):
        raise ValueError('Current reviewed parser binding differs from rich source parser')
    missing = missing_privileges(conn)
    if missing:
        raise MissingSourcePrivileges(missing)
    with conn.cursor() as cur:
        series_id, _ = _capture_context(cur, capture_id, source_sha256)
    result = persist_parse_snapshot(conn, capture_id=capture_id,
        parser_name=parser.PARSER_NAME, parser_revision=parser.PARSER_VERSION,
        code_revision=code_revision, configuration_hash=parser.PARSER_CONFIGURATION_HASH,
        started_at=started_at, completed_at=completed_at,
        records=records, diagnostics=_diagnostics(expected_count))
    with conn.cursor() as cur:
        schema_id = _schema(cur, series_id, started_at)
        definitions = {d['key']: _ensure_field_definition(cur, schema_id, d) for d in FIELD_DEFINITIONS}
        for record in records:
            record_id = _ensure_parsed_record(cur, result['parse_run_id'], schema_id, record)
            for definition in FIELD_DEFINITIONS:
                _ensure_field_value(cur, record_id, definitions[definition['key']], schema_id,
                    record[definition['key']], _parsed_value(record,definition),
                    definition['structural_locator'].split(':',1)[1])
            _ensure_entity_mention(cur, record_id)
    verified = verify_rich_readback(conn, capture_id=capture_id,
        parse_run_id=result['parse_run_id'],source_sha256=source_sha256,
        expected_count=expected_count,expected_snapshot_sha256=digest,code_revision=code_revision)
    return {**result, **verified}
