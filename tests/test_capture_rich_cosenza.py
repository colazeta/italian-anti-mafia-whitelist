import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from uuid import uuid4

import pytest

from white_list_archive.parsers import cosenza_combined_v2 as parser
from white_list_archive.persistence.capture_rich_cosenza import (
    INSERT_TABLES, MissingSourcePrivileges, missing_privileges, persist_capture_records, validate_records,
)


def synthetic_record():
    raw = 'Synthetic source row'
    name, identifier, outcome_raw = 'Synthetic Operator', '12345678901', 'In corso'
    outcome = parser._parse_outcome(outcome_raw)
    return {'row_ordinal':1,'operator_name_raw':name,
        'operator_name_normalised':parser.normalise_name(name),
        'registered_office_raw':'Synthetic office','secondary_office_raw':'',
        'identifier_field_raw':identifier,'identifiers_json':'[]',
        'requested_activities_raw':'','requested_activities_json':'[]',
        'application_date_field_raw':'','application_dates_json':'[]',
        'outcome_raw':outcome_raw,'outcome_json':json.dumps(outcome),
        'source_status':outcome['status'],
        'observed_listing_date':'','observed_expiry_date':'',
        'record_hash':hashlib.sha256(raw.encode()).hexdigest(),
        'mention_key':hashlib.sha256(('\x1f'.join([identifier,parser.normalise_name(name)])).encode()).hexdigest(),
        'raw_block':raw}


def test_rich_record_contract_hashing_is_deterministic_and_preserves_raw_values():
    rows = [synthetic_record()]
    original = copy.deepcopy(rows)
    assert validate_records(rows,1) == validate_records(copy.deepcopy(rows),1)
    assert rows == original


@pytest.mark.parametrize('field,value', [('row_ordinal',2),('record_hash','0'*64),
    ('mention_key','0'*64),('operator_name_normalised','altered'),
    ('identifiers_json','{}'),('outcome_json','[]')])
def test_malformed_rich_fields_fail_before_database_access(field,value):
    row = synthetic_record();row[field] = value
    now = datetime.now(timezone.utc)
    class NoDatabaseAccess:
        def cursor(self):
            pytest.fail('Malformed rich records must fail before database access')
    with pytest.raises((ValueError,TypeError)):
        persist_capture_records(NoDatabaseAccess(),capture_id=str(uuid4()),
            source_sha256='a'*64,records=[row],code_revision='b'*40,
            started_at=now,completed_at=now,expected_count=1)


def test_permission_check_has_fixed_append_only_requirements_and_reports_exact_missing():
    missing_tables = {'source.source_schema','source.source_schema_version',
        'source.source_field_definition','source.parsed_record','source.source_field_value','source.entity_mention'}
    class Cursor:
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def execute(self,sql,params):
            assert sql.startswith('SELECT ')
            assert 'GRANT' not in sql
            tables, privileges = params
            self.rows = [(t,p,not (t in missing_tables and p=='INSERT')) for t,p in zip(tables,privileges)]
        def fetchall(self):return self.rows
    class Connection:
        def cursor(self):return Cursor()
    result = missing_privileges(Connection())
    assert result == [{'table':t,'privilege':'INSERT'} for t in INSERT_TABLES if t in missing_tables]
    assert len(result) == 6
    assert not {'source.source_capture','source.content_object','source.source_series'} & set(INSERT_TABLES)


def test_workflow_defaults_to_read_only_and_persistence_requires_manual_event():
    text = (Path(__file__).resolve().parents[1]/'.github/workflows/cosenza-rich-preflight.yml').read_text()
    assert 'default: preflight' in text
    assert "PREFLIGHT_MODE: ${{ needs.authorise.outputs.mode }}" in text
    assert "mode == 'persist-source-only' and os.environ['GITHUB_EVENT_NAME'] in ('workflow_dispatch', 'issue_comment')" in text
    assert 'actions/upload-artifact' not in text
