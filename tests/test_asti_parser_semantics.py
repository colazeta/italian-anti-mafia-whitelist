from white_list_archive.parsers.asti_positioned import _activity_parts, _status_applicant


def test_asti_applicant_status_mapping_is_source_literal_and_conservative():
    assert _status_applicant('In istruttoria') == 'pending'
    assert _status_applicant('Iscritta il 24.08.2026') == 'listed'
    assert _status_applicant('Non iscritta') == 'other_or_unknown'
    assert _status_applicant('') == 'other_or_unknown'


def test_asti_multi_section_applicant_activity_is_split_without_relabelling():
    activities, sections = _activity_parts('SEZIONE IV Fornitura di ferro lavorato SEZIONE VI Autotrasporto conto terzi')
    assert sections == ['Sezione IV', 'Sezione VI']
    assert activities == ['Fornitura di ferro lavorato', 'Autotrasporto conto terzi']
