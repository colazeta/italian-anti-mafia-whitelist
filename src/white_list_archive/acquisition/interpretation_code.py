"""Conservative Git-object equivalence for private interpretation reuse.

Original processing revisions are never rewritten. Missing historical objects
mean no cross-revision reuse; this helper never fetches code or executes it.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
import re
import subprocess

_REVISION = re.compile(r"[0-9a-f]{40}")
# Cover every physical family, dispatcher/adapter, public record contract and
# declared runtime dependency. Acquisition/writer changes still independently
# verify provenance and complete inputs before reaching the reuse boundary.
INTERPRETATION_PATHS = (
    "src/white_list_archive/parsers",
    "src/white_list_archive/publishing",
    "src/white_list_archive/acquisition/national_index.py",
    "pyproject.toml",
)
# These two modules inspect already parsed output or prepare a release selector.
# Physical extraction/normalisation never imports them. Every other existing or
# newly added publishing object remains in the conservative interpretation key.
POST_INTERPRETATION_PATHS = frozenset({
    "src/white_list_archive/publishing/publication_handoff.py",
    "src/white_list_archive/publishing/como_review.py",
})


@lru_cache(maxsize=256)
def code_objects(revision: str, root: Path | None = None) -> bytes | None:
    if not isinstance(revision, str) or _REVISION.fullmatch(revision) is None:
        return None
    root = root or Path(__file__).resolve().parents[3]
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "ls-tree", revision, "--", *INTERPRETATION_PATHS],
            capture_output=True, check=True, timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    lines = result.stdout.splitlines()
    # An incomplete old tree cannot accidentally compare equal to another one.
    paths = {line.split(b"\t", 1)[-1].decode("utf-8") for line in lines}
    if paths != set(INTERPRETATION_PATHS):
        return None
    try:
        recursive = subprocess.run(
            ["git", "-C", str(root), "ls-tree", "-r", revision, "--", *INTERPRETATION_PATHS],
            capture_output=True, check=True, timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    retained = [line for line in recursive.stdout.splitlines()
                if line.split(b"\t", 1)[-1].decode("utf-8") not in POST_INTERPRETATION_PATHS]
    # Excluding downstream tools must not make an otherwise empty or incomplete
    # publishing tree appear to be a verified interpretation implementation.
    if not any(line.split(b"\t", 1)[-1].startswith(b"src/white_list_archive/publishing/")
               for line in retained):
        return None
    return b"\n".join(retained) + b"\n"


def equivalent_revision(previous: str, current: str) -> bool:
    if _REVISION.fullmatch(previous or "") is None or _REVISION.fullmatch(current or "") is None:
        return False
    if previous == current:
        return True
    before, after = code_objects(previous), code_objects(current)
    return before is not None and before == after
