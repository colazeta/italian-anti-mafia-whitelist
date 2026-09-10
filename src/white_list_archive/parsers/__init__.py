"""Parsers layer.

Parser families that can safely extend the shared multi-Prefecture dispatch registry
are registered here before callers import ``multi_prefecture_tables.PARSERS``.
"""

from white_list_archive.parsers import multi_prefecture_tables as _multi_prefecture_tables
from white_list_archive.parsers.belluno_combined import PARSERS as _BELLUNO_PARSERS

_multi_prefecture_tables.PARSERS.update(_BELLUNO_PARSERS)
