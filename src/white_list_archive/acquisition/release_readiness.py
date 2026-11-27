"""Read-only release triage from genuine archived inputs, independent of quarantines.

This bounded first cohort uses existing mutable HTML parser families. It prepares
review metadata; it cannot approve editions, change selection or publish records.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import date
from html.parser import HTMLParser
import hashlib
import json
from pathlib import Path
import re
import tempfile

from . import auto_transform as transform

COHORT = ("biella", "como", "taranto")
MONTHS = {name: index for index, name in enumerate((
    "gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno",
    "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre"), 1)}
WEEKDAYS = ("lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica")
# Exact reviewed official warning/authority/title/legal preamble cells. These
# hashes cover headings only, never company records; unknown prose still fails.
BIELLA_PREAMBLE_SHA256 = frozenset(["0cf4bb49c1a2dfc0e02126979884069b938a3552e95ce33bdb4e038eddcdbaf2","69536ae260595da143d3fe65e4ff9e5b28a6110a5d64644878e9c7721be67bb9","8fa0480e97e1061defc89f1e4efc6e96fa3c77f193d0b8c460eeb7b0308d7cd2","be629af2cb637c38d2a44817e213e40c70e1e34c40e6831f95f53caa2b177e99","c9579067f05f8ce4f9f632d464ecbb79e443a290541f111ab8810e7b50a3225b","e6d8ca4d8ba443bc1c9e1909a46e3d388357b11ce2342623695c597eea4ba3db"])


class _VisibleText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.suppressed = 0
    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style"}: self.suppressed += 1
    def handle_endtag(self, tag):
        if tag in {"script", "style"}: self.suppressed = max(0, self.suppressed - 1)
    def handle_data(self, text):
        if not self.suppressed: self.parts.append(text)


def explicit_update_date(raw: bytes, captured_at: str) -> str:
    """Require one explicit page-update date; capture time never supplies a date."""
    parser = _VisibleText()
    parser.feed(raw.decode("utf-8"))
    parser.close()
    text = " ".join(" ".join(parser.parts).split()).casefold()
    weekdays = "|".join(WEEKDAYS)
    # Inspect every declaration, including unsupported date formats. Looking
    # only for successful matches would silently ignore a conflicting label.
    labels = list(re.finditer(r"\bultimo aggiornamento", text))
    pattern = re.compile(r"\s*:?\s*(?:(" + weekdays +
                         r")\s+)?([0-9]{1,2})\s+([a-z]+)\s+([0-9]{4})"
                         r"(?![\w/-]|\.[0-9])")
    values = set()
    for index, label in enumerate(labels):
        end = labels[index + 1].start() if index + 1 < len(labels) else len(text)
        found = pattern.match(text, label.end(), end)
        if found is None:
            raise ValueError("Unrecognised explicit source update declaration")
        weekday, day, month, year = found.groups()
        if month not in MONTHS: raise ValueError("Unrecognised explicit source month")
        declared = date(int(year), MONTHS[month], int(day))
        if weekday and WEEKDAYS[declared.weekday()] != weekday:
            raise ValueError("Conflicting explicit source weekday")
        values.add(declared.isoformat())
    instant = transform._capture_timestamp_utc(captured_at)
    if len(values) != 1 or instant is None or next(iter(values)) > instant.date().isoformat():
        raise ValueError("Missing, ambiguous or future explicit source update date")
    return next(iter(values))


def biella_complete_physical_rows(path: Path, population: str) -> int:
    """Census every nonempty row, including widths the legacy parser skips."""
    from white_list_archive.parsers import biella_html as family
    tables = family._tables(path)
    if population == "listed":
        table = family._find_listed_table(tables)
        header = family._LISTED_HEADER
        width = 7
        title = family._LISTED_TITLE
    elif population == "applicant":
        table = family._find_applicant_table(tables)
        header = family._APPLICANT_HEADER
        width = 8
        title = family._APPLICANT_TITLE
    else:
        raise ValueError("Unknown Biella population")
    candidates = 0
    awaiting_activity = False
    for row in table:
        cleaned = [family._clean(v) for v in row]
        if not any(cleaned): continue
        first, rest = cleaned[0], cleaned[1:]
        folded = family._row_fold(row)
        if not any(rest) and hashlib.sha256(first.encode()).hexdigest() in BIELLA_PREAMBLE_SHA256:
            continue
        if first == title and not any(rest): continue
        if first.casefold() == "prefettura di biella" and not any(rest): continue
        if population == "listed" and first.casefold().startswith("sezione ") and not any(rest):
            awaiting_activity = True
            continue
        if awaiting_activity and len(row) == 1 and first:
            awaiting_activity = False
            continue
        if len(row) == width and folded[:7] == header: continue
        if len(row) != width or not first or not cleaned[3]:
            raise ValueError("Unclassified nonempty Biella physical row")
        candidates += 1
    if awaiting_activity or not candidates:
        raise ValueError("Incomplete Biella section or no physical observations")
    return candidates


class ComoCensusError(ValueError):
    """Safe structural diagnostics, never source cell values."""
    def __init__(self, message, values):
        super().__init__(message)
        self.metadata = {'row_width': len(values), 'nonempty_cells': sum(bool(v) for v in values),
                         'first_cell_sha256': hashlib.sha256(values[0].encode()).hexdigest(),
                         'is_authority_heading': values[0].casefold() == 'prefettura di como'}


# Literal official headings, legal reference, portal notice and sector legend,
# independently inspected on both official pages; no company observation hashes.
COMO_PREAMBLE_SHA256 = frozenset({
    '8d95bab7879bdce11aaf6614a9c2ebed8730c8b52ecabf1b8939d21457dda29f',
    '61154f2a8bab2dfcb2aa6c0c0ea46874317214043ddb4af4c83858d4e736dd71',
    'cf7aad8af439460d0672e2fe4394175c4ff860c6227a7083d2d4bea58931e304',
    '5b0541c7234d00ba6e603c9a72c71286b90ae93ee04652f77edb546d8d3aebc6',
    'aa32ba55c30505bf47cbb265b8bd91dcc80cf4c8aa2ced23d765438aa8311f37',
})


def como_complete_physical_rows(path: Path, population: str) -> int:
    """Classify every nonempty row, including rows the family would skip."""
    from white_list_archive.parsers import como_html as family
    if population not in {"listed", "applicant"}:
        raise ValueError("Unknown Como population")
    applicant = population == "applicant"
    title = family._APPLICANT_TITLE if applicant else family._LISTED_TITLE
    header = family._APPLICANT_HEADER if applicant else family._LISTED_HEADER
    label = "numero aziende in fase iscrizione:" if applicant else "numero aziende iscritte:"
    table = family._find_table(family._tables(path), applicant=applicant)
    rows, summaries, headers = 0, 0, 0
    for row in table:
        values = [family._clean(value) for value in row]
        if not any(values):
            continue
        if not headers and values[0].casefold() == title.casefold() and not any(values[1:]):
            continue
        # Both independently pinned November originals have these two-cell
        # authority captions (SHA2565cd7775c... and089e6344...). Empty tails only.
        if not headers and len(values) == 2 and values[0].casefold() in {
                'prefettura di como', 'ufficio territoriale del governo'} and not values[1]:
            continue
        if not headers and not any(values[1:]) and hashlib.sha256(values[0].encode()).hexdigest() in COMO_PREAMBLE_SHA256:
            continue
        if len(values) == 8 and family._fold(values) == header:
            if headers:
                raise ComoCensusError('Repeated Como table header', values)
            headers += 1
            continue
        if len(values) == 8 and values[0].casefold() == label:
            if headers or not values[1].isdigit() or any(values[2:]):
                raise ComoCensusError("Unclassified Como source counter", values)
            summaries += 1
            continue
        if headers != 1 or len(values) != 8 or not values[0] or not any(values[1:]):
            raise ComoCensusError("Unclassified nonempty Como physical row", values)
        rows += 1
    if not rows or summaries != 1:
        raise ValueError("Incomplete Como physical source census")
    return rows


def taranto_complete_physical_rows(path: Path, population: str) -> int:
    """Independent fail-closed census of the complete Taranto evidence table.

    This deliberately examines raw physical cells instead of using the family
    parser's _find_rows output, which may discard content before its header.
    An unexpected caption, header, row width or incomplete row is a review gate.
    """
    from white_list_archive.parsers import taranto_html as family
    if population not in {"listed", "applicant"}:
        raise ValueError("Unknown Taranto population")
    header = family._LISTED_HEADER if population == "listed" else family._APPLICANT_HEADER
    width = len(header)
    selected = []
    for table in family._tables(path):
        for row in table:
            values = [family._clean(value) for value in row]
            if values and values[0].casefold() == header[0] and family._fold(row) != header:
                raise ValueError("Unreviewed Taranto table header drift")
        positions = [index for index, row in enumerate(table) if family._fold(row) == header]
        if positions:
            if len(positions) != 1:
                raise ValueError("Repeated Taranto evidence table header")
            selected.append((table, positions[0]))
    if len(selected) != 1:
        raise ValueError("Missing or ambiguous Taranto evidence table")
    table, header_index = selected[0]
    if any(any(family._clean(value) for value in row) for row in table[:header_index]):
        raise ValueError("Unreviewed Taranto pre-header physical row")
    count = 0
    for row in table[header_index + 1:]:
        values = [family._clean(value) for value in row]
        if not any(values):
            continue
        if len(values) != width or not values[0] or not any(values[1:]) or family._fold(row) == header:
            raise ValueError("Unclassified nonempty Taranto physical row")
        count += 1
    if count == 0:
        raise ValueError("No complete Taranto physical observations")
    return count



# Fixed pair: review only, not an approved publication profile.
_BIELLA_DELTA_SHA = "60fa8903200505d0621f17685fb9520ed129cdf71cdd8bb582e132743fad23ca"
_BIELLA_DELTA_DATE = "2026-11-25"
_BIELLA_DELTA_BYTES = 204481
_BIELLA_DELTA_COUNTERS = frozenset({
    "old_observations", "new_observations", "old_only_text_keys", "new_only_text_keys",
    "shared_text_keys", "shared_keys_changed_multiplicity", "shared_keys_changed_status",
    "shared_keys_changed_values", "old_unmatched_observations", "new_unmatched_observations",
    "old_identifier_shape_rows", "new_identifier_shape_rows",
    "old_other_field_shape_rows", "new_other_field_shape_rows",
})
# Broad shape clue, including omocodia-like values; never a verified tax code.
_CF_SHAPE = re.compile(r"(?<![A-Za-z0-9])[A-Za-z]{6}[A-Za-z0-9]{2}[A-Za-z][A-Za-z0-9]{2}[A-Za-z][A-Za-z0-9]{3}[A-Za-z](?![A-Za-z0-9])")


def _contains_cf_shape(value):
    if isinstance(value, str):
        return bool(_CF_SHAPE.search(value))
    if isinstance(value, list):
        return any(_contains_cf_shape(item) for item in value)
    if isinstance(value, dict):
        return any(_contains_cf_shape(item) for item in value.values())
    return False


def biella_observation_delta(old, new):
    """Compare exact documentary text keys and multisets; never resolve entities."""
    ignored = {"record_locator", "source_row_ordinal", "reference_date", "capture_sha256"}
    def grouped(rows):
        groups = {}
        for row in rows:
            key = (row["name"], row["identifier_field_raw"])
            value = json.dumps({k: v for k, v in row.items() if k not in ignored},
                               sort_keys=True, ensure_ascii=False)
            entries = groups.setdefault(key, (Counter(), Counter()))
            entries[0][value] += 1
            entries[1][row["source_status"]] += 1
        return groups
    a, b = grouped(old), grouped(new)
    shared = a.keys() & b.keys()
    def unmatched(left, right):
        return sum(sum((values[0] - right.get(key, (Counter(), Counter()))[0]).values())
                   for key, values in left.items())
    result = {
        "old_observations": len(old), "new_observations": len(new),
        "old_only_text_keys": len(a.keys() - b.keys()), "new_only_text_keys": len(b.keys() - a.keys()),
        "shared_text_keys": len(shared),
        "shared_keys_changed_multiplicity": sum(sum(a[k][0].values()) != sum(b[k][0].values()) for k in shared),
        "shared_keys_changed_status": sum(a[k][1] != b[k][1] for k in shared),
        "shared_keys_changed_values": sum(a[k][0] != b[k][0] for k in shared),
        "old_unmatched_observations": unmatched(a, b), "new_unmatched_observations": unmatched(b, a),
    }
    for label, rows in (("old", old), ("new", new)):
        identifier_fields = {"identifier_field_raw", "identifiers"}
        result[label + "_identifier_shape_rows"] = sum(
            _contains_cf_shape({k: v for k, v in row.items() if k in identifier_fields}) for row in rows)
        result[label + "_other_field_shape_rows"] = sum(
            _contains_cf_shape({k: v for k, v in row.items() if k not in identifier_fields | ignored}) for row in rows)
    return result


def _biella_pinned_delta(store, job, manifest, new_records, updated):
    from white_list_archive.publishing import biella_review
    from white_list_archive.publishing.public_contract import public_record
    cfg = job["config"]
    if (cfg.get("sha256") != biella_review.SOURCE_SHA256
            or cfg.get("reference_date") != biella_review.REFERENCE_DATE
            or manifest.get("sha256") != _BIELLA_DELTA_SHA
            or manifest.get("byte_size") != _BIELLA_DELTA_BYTES
            or updated != _BIELLA_DELTA_DATE):
        return {"status": "outside_frozen_pair"}
    try:
        raw = store.read_digest_verified(biella_review.SOURCE_SHA256)
        with tempfile.TemporaryDirectory(prefix="biella-delta-review-") as td:
            path = Path(td) / "previous.html"
            path.write_bytes(raw)
            # Existing finite profile independently rechecks the old exact bytes,
            # date, physical census and complete semantic digest before comparison.
            old = biella_review.qualify(path, cfg, checked_at=manifest["captured_at"])
        return {"status": "documentary_comparison_ready",
                **biella_observation_delta([public_record(r) for r in old.records], new_records)}
    except Exception:
        return {"status": "comparison_requires_review"}


def inspect_job(job, store):
    """Strict source triage; QA drift from the old edition remains explicit."""
    from white_list_archive.publishing import public_national_registry as registry
    from white_list_archive.publishing.public_contract import public_record
    if set(job["captures"]) != {"primary"}:
        raise ValueError("Readiness cohort requires one complete scalar input")
    cfg = transform._parse_config(job)
    manifest, _, raw = transform._verified_capture(store, job["captures"]["primary"])
    updated = explicit_update_date(raw, manifest["captured_at"])
    cfg["reference_date"] = updated
    with tempfile.TemporaryDirectory(prefix="white-list-readiness-") as td:
        path = Path(td) / "source.html"
        path.write_bytes(raw)
        batch = registry._parse_source(path, cfg)
        if not batch.records or batch.diagnostics.get("dropped_date_rows", 0):
            raise ValueError("Empty or incomplete source extraction")
        public_records = [public_record(record) for record in batch.records]
        from white_list_archive.publishing.publication_handoff import records_digest
        physical = None
        if cfg["authority_key"] == "biella":
            physical = biella_complete_physical_rows(path, cfg["population_scope"])
            if physical != batch.diagnostics.get("sector_rows"):
                raise ValueError("Physical source denominator mismatch")
        elif cfg["authority_key"] == "como":
            physical = como_complete_physical_rows(path, cfg["population_scope"])
            if physical != batch.diagnostics.get("source_rows") or physical != len(batch.records):
                raise ValueError("Como physical source denominator mismatch")
        elif cfg["authority_key"] == "taranto":
            physical = taranto_complete_physical_rows(path, cfg["population_scope"])
            if physical != batch.diagnostics.get("source_rows") or physical != len(batch.records):
                raise ValueError("Taranto physical source denominator mismatch")
    delta = (_biella_pinned_delta(store, job, manifest, public_records, updated)
             if cfg["authority_key"] == "biella" else None)
    return {
        "biella_documentary_delta": delta,
        "source_key": job["source_key"], "status": "source_candidate_requires_review",
        "sha256": manifest["sha256"], "bytes": manifest["byte_size"],
        "reference_date": updated, "previous_reference_date": job["config"].get("reference_date"),
        "date_basis": "explicit_official_page_update_not_administrative_event",
        "parser": cfg["parser"], "parser_revision": transform._parser_revision(batch, cfg["parser"]),
        "records": len(batch.records), "physical_rows": physical,
        "semantic_sha256": registry._semantic_digest(batch.records),
        "public_records_sha256": records_digest(public_records),
        "blank_names": sum(not row["name"] for row in public_records),
        "blank_activities": sum(not row["requested_activities"] for row in public_records),
        "diagnostics": batch.diagnostics,
        "previous_edition_qa_differences": transform._quality_flags(job["config"], batch.records, batch.diagnostics),
        "original_and_capture_provenance_verified": True,
        "publication_approved": False,
    }


def triage(jobs, inspect):
    """A bad population or authority cannot stop another authority's review."""
    results = []
    groups = {}
    for job in jobs:
        authority = job["config"]["authority_key"]
        if authority in COHORT: groups.setdefault(authority, []).append(job)
    for authority in COHORT:
        selected = groups.get(authority, [])
        if Counter(j["config"]["population_scope"] for j in selected) != {"listed": 1, "applicant": 1}:
            results.append({"authority_key": authority, "status": "incomplete_population_inputs"})
            continue
        outcomes = []
        for job in sorted(selected, key=lambda j: j["source_key"]):
            try: outcomes.append(inspect(job))
            except Exception as exc:
                outcomes.append({"source_key": job["source_key"], "status": "requires_source_review",
                                 "error_type": type(exc).__name__, "publication_approved": False})
        results.append({"authority_key": authority, "status": "review_metadata_ready" if all(
            row["status"] == "source_candidate_requires_review" for row in outcomes) else "requires_source_review",
            "sources": outcomes})
    return {"kind": "archived-release-readiness", "schema_version": 1,
            "results": results, "publications": 0, "approvals": 0}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--source-config", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        from white_list_archive.storage.evidence import EvidenceStore, StoreConfig, client_for
        config = StoreConfig.from_env()
        store = EvidenceStore(client_for(config), config)
        jobs, _ = transform.select_reviewed_jobs(
            json.loads(args.state.read_text()), json.loads(args.source_config.read_text()),
            include_unchanged=True,
        )
        report = triage(jobs, lambda job: inspect_job(job, store))
        transform.persist_operational_report(store, report)
    except Exception:
        print(json.dumps({"readiness_operational_status": "failed", "publications": 0, "approvals": 0}))
        return 1
    # Counts/dates/source content identities are safe operational metadata.
    # No names, row locators, raw text, provider coordinates or exception messages.
    print(json.dumps(public_summary(report), sort_keys=True))
    return 0


def public_summary(report):
    """Closed source-level counters; private diagnostics can never expand logs."""
    numeric = {"sector_rows", "public_records", "identifier_coverage", "raw_identifier_only",
               "missing_application_dates", "missing_expiry_dates", "grouped_sector_repetitions",
               "dropped_date_rows", "unique_source_identities", "source_rows", "declared_count",
               "declared_count_delta", "blank_identifier_rows", "malformed_date_rows"}
    allowed = {"source_key", "status", "sha256", "bytes", "reference_date", "previous_reference_date",
               "date_basis", "parser", "parser_revision", "records", "physical_rows", "semantic_sha256",
               "original_and_capture_provenance_verified", "publication_approved", "error_type"}
    result = {"kind": report["kind"], "schema_version": 1, "publications": 0, "approvals": 0, "results": []}
    for group in report["results"]:
        safe = {"authority_key": group["authority_key"], "status": group["status"], "sources": []}
        for row in group.get("sources", []):
            projected = {k: v for k, v in row.items() if k in allowed}
            digest = row.get("public_records_sha256")
            if isinstance(digest, str) and re.fullmatch(r"[0-9a-f]{64}", digest):
                projected["public_records_sha256"] = digest
            for name in ("blank_names", "blank_activities"):
                value = row.get(name)
                if type(value) is int and value >= 0:
                    projected[name] = value
            diag = row.get("diagnostics", {})
            projected["quality_counts"] = {k: v for k, v in diag.items() if k in numeric and type(v) is int}
            projected["status_counts"] = {k: v for k, v in diag.get("status_counts", {}).items()
                if k in {"listed", "pending", "renewal_update_in_progress", "other_or_unknown"} and type(v) is int}
            delta = row.get("biella_documentary_delta")
            if isinstance(delta, dict) and delta.get("status") in {
                    "outside_frozen_pair", "comparison_requires_review", "documentary_comparison_ready"}:
                projected["biella_documentary_delta"] = {"status": delta["status"], **{
                    k: v for k, v in delta.items() if k in _BIELLA_DELTA_COUNTERS and type(v) is int and v >= 0}}
            safe["sources"].append(projected)
        result["results"].append(safe)
    return result


if __name__ == "__main__": raise SystemExit(main())
