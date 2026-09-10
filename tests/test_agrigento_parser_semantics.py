from dataclasses import dataclass

from white_list_archive.parsers.agrigento_positioned import (
    _maximal_rows,
    _safe_source_date,
    _section_labels,
)


@dataclass
class _Row:
    cells: list[tuple[float, float, float, float] | None]


@dataclass
class _Table:
    rows: list[_Row]


def _row(y_min: float, y_max: float) -> _Row:
    return _Row(cells=[(0.0, y_min, 10.0, y_max)])


def test_agrigento_maximal_rows_excludes_strictly_nested_micro_grid_rows():
    outer = _row(10.0, 30.0)
    nested = _row(14.0, 20.0)
    independent = _row(31.0, 42.0)

    logical, nested_count = _maximal_rows(_Table(rows=[outer, nested, independent]))

    assert [row for row, _ in logical] == [outer, independent]
    assert nested_count == 1


def test_agrigento_date_normalisation_is_whitespace_only_and_fail_closed():
    assert _safe_source_date('06.08. 2020') == '2020-08-06'
    assert _safe_source_date('26.062026') == ''
    assert _safe_source_date('01..04.2026') == ''
    assert _safe_source_date('20,08,2026') == ''


def test_agrigento_section_labels_do_not_infer_missing_section_numbers():
    assert _section_labels('1, 3, 10') == ['Sezione 1', 'Sezione 3', 'Sezione 10']
    assert _section_labels(',') == []
    assert _section_labels('Sezione 4') == []
