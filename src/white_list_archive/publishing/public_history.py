"""Aggregate-only, append-preserving history of approved public White List editions.

Document checks concern approved resources, not exhaustive discovery of everything
published by a Prefecture. No company names, tax identifiers or row fingerprints
are persisted in this ledger. Missing identity comparisons remain null.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from copy import deepcopy
from datetime import date, datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import Any
import unicodedata
from urllib.request import Request, urlopen

VERSION = 1
PUBLIC_BASE = "https://colazeta.github.io/italian-anti-mafia-whitelist"
STATUSES = frozenset({"listed", "pending", "renewal_update_in_progress", "renewal_requested", "expired_observed", "rejected_or_denied", "cancellation_related", "other_or_unknown"})
EDITION_FIELDS = frozenset("id source_key authority_key authority_name register_key register_name population_scope reference_date reference_date_raw document_sha256 parser_signature total status_counts data_fingerprint source_page_url resource_url evidence".split())
CHECK_FIELDS = frozenset({"edition_id", "checked_at", "kind"})
COMPARISON_FIELDS = frozenset("before_id after_id basis added disappeared common content_changed status_changed unresolved_before unresolved_after transition_counts evidence".split())
CONTENT_FIELDS = ("name", "registered_office", "secondary_office", "identifier_field_raw", "requested_activities", "requested_activities_raw", "source_status", "outcome_raw", "application_date", "observed_listing_date", "decision_date", "registration_date", "observed_expiry_date")
HEX = re.compile(r"^[0-9a-f]{64}$")
BUNDLE_CAPTURE = re.compile(r"^bundle:([0-9a-f]{64})$")


def empty_history() -> dict:
    return {"version": VERSION, "editions": [], "checks": [], "comparisons": []}


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _history_document_sha256(capture_identity: str) -> str:
    """Return the content digest represented by an approved scalar or bundle capture identity."""
    if not isinstance(capture_identity, str):
        raise ValueError("Public capture content identity must be a string")
    if HEX.fullmatch(capture_identity):
        return capture_identity
    match = BUNDLE_CAPTURE.fullmatch(capture_identity)
    if match:
        return match.group(1)
    raise ValueError("Invalid public capture content identity")


def _normal(value: Any) -> Any:
    if isinstance(value, str):
        return " ".join(unicodedata.normalize("NFKC", value).split())
    if isinstance(value, list):
        return sorted((_normal(x) for x in value), key=lambda x: json.dumps(x, sort_keys=True))
    if isinstance(value, dict):
        return {k: _normal(v) for k, v in value.items()}
    return value


def _content(row: dict) -> dict:
    result = {key: _normal(row.get(key, "")) for key in CONTENT_FIELDS}
    result["identifiers"] = _normal(row.get("identifiers", []))
    result["source_fields"] = _normal({k: v for k, v in row.get("source_fields", {}).items() if k not in {"physical_locator", "physical_locators"}})
    return result


def iso_date(value: str) -> str | None:
    """Accept only complete, genuine ISO dates. Never substitute a check date."""
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return None
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError:
        return None


def _time(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("History check timestamp must be a string")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("History check timestamp needs a timezone")
    return parsed.astimezone(timezone.utc).isoformat()


def scope(edition: dict) -> tuple:
    return tuple(edition[k] for k in ("authority_key", "register_key", "population_scope", "source_key"))


def edition_id(edition: dict) -> str:
    return _digest([*scope(edition), edition["reference_date_raw"], edition["document_sha256"], edition["parser_signature"]])


def _counts(value: dict, allowed: frozenset | None = None) -> None:
    if not isinstance(value, dict) or (allowed is not None and value.keys() - allowed):
        raise ValueError("Unapproved history count keys")
    if any(type(n) is not int or n < 0 for n in value.values()):
        raise ValueError("History counts must be non-negative integers")


def validate_history(history: dict) -> None:
    """Recursively closed publication contract; fail on conflicts, not overwrite."""
    if set(history) != {"version", "editions", "checks", "comparisons"} or history["version"] != VERSION:
        raise ValueError("Unapproved history envelope")
    if any(not isinstance(history[key], list) for key in ("editions", "checks", "comparisons")):
        raise ValueError("History collections must be lists")
    editions = {}
    for item in history["editions"]:
        if set(item) != EDITION_FIELDS:
            raise ValueError("Unapproved history edition fields")
        if any(not isinstance(item[k], str) for k in EDITION_FIELDS - {"reference_date", "total", "status_counts", "data_fingerprint", "evidence"}):
            raise ValueError("History edition text expected")
        if item["reference_date"] != iso_date(item["reference_date_raw"]):
            raise ValueError("Unknown or incomplete dates must remain unknown")
        if not HEX.fullmatch(item["document_sha256"]) or item["id"] != edition_id(item):
            raise ValueError("Invalid history edition identity")
        if item["data_fingerprint"] is not None and (not isinstance(item["data_fingerprint"], str) or not HEX.fullmatch(item["data_fingerprint"])):
            raise ValueError("Invalid whole-edition data fingerprint")
        _counts(item["status_counts"], STATUSES)
        if type(item["total"]) is not int or item["total"] != sum(item["status_counts"].values()):
            raise ValueError("History total does not reconcile with statuses")
        if not isinstance(item["evidence"], list) or any(not isinstance(x, str) for x in item["evidence"]):
            raise ValueError("History evidence paths expected")
        for key in ("source_page_url", "resource_url"):
            if not item[key].startswith("https://"):
                raise ValueError("HTTPS source URL expected")
        if item["id"] in editions:
            raise ValueError("Duplicate history edition")
        editions[item["id"]] = item
    seen = set()
    for check in history["checks"]:
        if set(check) != CHECK_FIELDS or check["edition_id"] not in editions:
            raise ValueError("Invalid history check")
        if check["kind"] not in {"approved_document_verification", "historical_capture"} or _time(check["checked_at"]) != check["checked_at"]:
            raise ValueError("Invalid check kind or non-canonical timestamp")
        key = tuple(check[k] for k in sorted(CHECK_FIELDS))
        if key in seen:
            raise ValueError("Duplicate history check")
        seen.add(key)
    seen = set()
    for change in history["comparisons"]:
        if set(change) != COMPARISON_FIELDS or change["before_id"] not in editions or change["after_id"] not in editions:
            raise ValueError("Invalid history comparison")
        before, after = editions[change["before_id"]], editions[change["after_id"]]
        if scope(before) != scope(after) or before["parser_signature"] != after["parser_signature"]:
            raise ValueError("Cannot compare incompatible scopes or parser versions")
        if change["basis"] not in {"frozen_observational_diff", "exact_identifier_observations_v1", "capture_ordered_identifier_observations_v1"}:
            raise ValueError("Unapproved comparison basis")
        if change["basis"] == "capture_ordered_identifier_observations_v1":
            # Capture ordering is an observation chronology only. It is allowed
            # precisely where source-declared chronology is equal or unknown;
            # distinct known source dates continue to use the source-date basis.
            if before["reference_date"] and after["reference_date"] and before["reference_date"] != after["reference_date"]:
                raise ValueError("Capture-ordered comparison cannot override distinct known source dates")
            before_checks = [_time(c["checked_at"]) for c in history["checks"] if c["edition_id"] == before["id"]]
            after_checks = [_time(c["checked_at"]) for c in history["checks"] if c["edition_id"] == after["id"]]
            if not before_checks or not after_checks or max(before_checks) >= max(after_checks):
                raise ValueError("Capture-ordered comparison needs strictly ordered successful checks")
        elif not before["reference_date"] or not after["reference_date"] or before["reference_date"] >= after["reference_date"]:
            raise ValueError("A source-date comparison needs ordered, distinct known dates")
        for key in ("added", "disappeared", "common", "content_changed", "status_changed", "unresolved_before", "unresolved_after"):
            value = change[key]
            if value is not None and (type(value) is not int or value < 0):
                raise ValueError("Invalid comparison count")
        if any(change[k] is None for k in ("common", "content_changed", "status_changed")):
            raise ValueError("Match accounting must be explicit")
        if change["basis"] != "frozen_observational_diff" and any(change[k] is None for k in ("unresolved_before", "unresolved_after")):
            raise ValueError("Automatic identity comparison needs explicit unresolved accounting")
        if not change["status_changed"] <= change["content_changed"] <= change["common"]:
            raise ValueError("Changed rows do not reconcile")
        if (change["added"] is None) != (change["disappeared"] is None):
            raise ValueError("Both unpaired counts must be unknown together")
        if change["added"] is not None:
            if change["unresolved_before"] or change["unresolved_after"]:
                raise ValueError("Ambiguous observations cannot yield complete entry/exit counts")
            if before["total"] != change["common"] + change["disappeared"] or after["total"] != change["common"] + change["added"]:
                raise ValueError("Comparison counts do not reconcile with editions")
        if change["common"] + (change["unresolved_before"] or 0) > before["total"] or change["common"] + (change["unresolved_after"] or 0) > after["total"]:
            raise ValueError("Match counts exceed population")
        _counts(change["transition_counts"])
        for transition in change["transition_counts"]:
            parts = transition.split("->")
            if len(parts) != 2 or any(x not in STATUSES for x in parts) or parts[0] == parts[1]:
                raise ValueError("Unapproved status transition")
        if sum(change["transition_counts"].values()) != change["status_changed"]:
            raise ValueError("Status transitions do not reconcile")
        if not isinstance(change["evidence"], list) or any(not isinstance(x, str) for x in change["evidence"]):
            raise ValueError("Comparison evidence paths expected")
        key = (change["before_id"], change["after_id"], change["basis"])
        if key in seen:
            raise ValueError("Duplicate history comparison")
        seen.add(key)


def aggregate_registry(registry: dict) -> dict:
    from white_list_archive.publishing.public_contract import validate_registry
    validate_registry(registry)
    grouped = defaultdict(list)
    for row in registry["records"]:
        grouped[(row["source_key"], row["reference_date"], row["capture_sha256"])].append(row)
    result = empty_history()
    for report in registry["meta"]["sources"]:
        rows = grouped[(report["source_key"], report["reference_date"], report["sha256"])]
        first = rows[0]
        signatures = {f"{r['parser_name']}@{r.get('parser_version', '')}" for r in rows}
        if len(signatures) != 1 or any(scope(r) != scope(first) for r in rows):
            raise ValueError("One public edition cannot mix scope or parser versions")
        edition = {k: first[k] for k in ("source_key", "authority_key", "authority_name", "register_key", "register_name", "population_scope", "source_page_url", "resource_url")}
        edition.update(reference_date=iso_date(first["reference_date"]), reference_date_raw=first["reference_date"], document_sha256=_history_document_sha256(first["capture_sha256"]), parser_signature=next(iter(signatures)), total=len(rows), status_counts=dict(sorted(Counter(r["source_status"] for r in rows).items())), data_fingerprint=_digest(sorted(_digest(_content(r)) for r in rows)), evidence=["approved-public-registry"])
        edition["id"] = edition_id(edition)
        result["editions"].append(edition)
        if report.get("document_checked_at"):
            result["checks"].append({"edition_id": edition["id"], "checked_at": _time(report["document_checked_at"]), "kind": "approved_document_verification"})
    validate_history(result)
    return result


def merge_histories(*histories: dict) -> dict:
    editions, checks, comparisons = {}, {}, {}
    for history in histories:
        validate_history(history)
        for source in history["editions"]:
            item = deepcopy(source)
            old = editions.get(item["id"])
            if old:
                # Counts and evidence identities are immutable. A whole-edition
                # fingerprint may enrich a frozen aggregate once, not replace it.
                fixed = EDITION_FIELDS - {"evidence", "data_fingerprint"}
                if any(old[k] != item[k] for k in fixed):
                    raise ValueError("Conflicting history edition; keep both parser revisions instead")
                if old["data_fingerprint"] and item["data_fingerprint"] and old["data_fingerprint"] != item["data_fingerprint"]:
                    raise ValueError("Same bytes/parser produced different data; version the parser")
                item["data_fingerprint"] = old["data_fingerprint"] or item["data_fingerprint"]
                item["evidence"] = sorted(set(old["evidence"] + item["evidence"]))
            editions[item["id"]] = item
        for check in history["checks"]:
            checks[tuple(check[k] for k in sorted(CHECK_FIELDS))] = deepcopy(check)
        for item in history["comparisons"]:
            key = (item["before_id"], item["after_id"], item["basis"])
            if key in comparisons and comparisons[key] != item:
                raise ValueError("Conflicting immutable history comparison")
            comparisons[key] = deepcopy(item)
    result = {"version": VERSION, "editions": sorted(editions.values(), key=lambda e: (*scope(e), e["reference_date"] or "", e["id"])), "checks": sorted(checks.values(), key=lambda c: (c["checked_at"], c["edition_id"], c["kind"])), "comparisons": sorted(comparisons.values(), key=lambda c: (c["before_id"], c["after_id"], c["basis"]))}
    validate_history(result)
    return result


def _identifier_key(row: dict) -> str | None:
    values = []
    for item in row.get("identifiers", []):
        value = item if isinstance(item, str) else item.get("raw_value", "")
        value = re.sub(r"\s+", "", value).upper()
        if not re.fullmatch(r"(?:\d{11}|[A-Z0-9]{16})", value):
            return None
        values.append(value)
    # An exact complete identifier bundle is only an observational link, never
    # a canonical entity key. Invalid/missing/composite ambiguity is left open.
    return "|".join(sorted(set(values))) if values else None


def compare_rows(before: list[dict], after: list[dict], before_id: str, after_id: str, basis: str = "exact_identifier_observations_v1") -> dict:
    if basis not in {"exact_identifier_observations_v1", "capture_ordered_identifier_observations_v1"}:
        raise ValueError("Unapproved automatic comparison basis")
    def index(rows: list[dict]) -> tuple[dict, int]:
        groups = defaultdict(list)
        for row in rows:
            groups[_identifier_key(row)].append(row)
        unique = {k: v[0] for k, v in groups.items() if k is not None and len(v) == 1}
        return unique, sum(len(v) for k, v in groups.items() if k is None or len(v) != 1)
    left, unresolved_left = index(before)
    right, unresolved_right = index(after)
    # Overlapping but changed identifier bundles are ambiguous, not entries/exits.
    changed_bundles = set()
    for a in set(left) - set(right):
        if any(set(a.split("|")) & set(b.split("|")) for b in set(right) - set(left)):
            changed_bundles.add(a)
    for b in set(right) - set(left):
        if any(set(b.split("|")) & set(a.split("|")) for a in set(left) - set(right)):
            changed_bundles.add(b)
    for key in changed_bundles:
        if key in left:
            unresolved_left += 1
            del left[key]
        if key in right:
            unresolved_right += 1
            del right[key]
    # Identifier reuse with a changed name needs stronger identity evidence.
    for key in list(left.keys() & right.keys()):
        if _normal(left[key].get("name", "")) != _normal(right[key].get("name", "")):
            del left[key]
            del right[key]
            unresolved_left += 1
            unresolved_right += 1
    common = left.keys() & right.keys()
    transitions = Counter(f"{left[k]['source_status']}->{right[k]['source_status']}" for k in common if left[k]["source_status"] != right[k]["source_status"])
    complete = not (unresolved_left or unresolved_right)
    return {"before_id": before_id, "after_id": after_id, "basis": basis, "added": len(right.keys() - left.keys()) if complete else None, "disappeared": len(left.keys() - right.keys()) if complete else None, "common": len(common), "content_changed": sum(_content(left[k]) != _content(right[k]) for k in common), "status_changed": sum(transitions.values()), "unresolved_before": unresolved_left, "unresolved_after": unresolved_right, "transition_counts": dict(sorted(transitions.items())), "evidence": ["approved-public-registry", basis]}


def compare_releases(previous: dict, current: dict) -> dict:
    old, new = aggregate_registry(previous), aggregate_registry(current)
    result = merge_histories(old, new)
    old_by_scope = defaultdict(list)
    for edition in old["editions"]:
        old_by_scope[scope(edition)].append(edition)

    def rows_for(registry: dict, edition: dict) -> list[dict]:
        return [r for r in registry["records"] if (r["source_key"], r["reference_date"], _history_document_sha256(r["capture_sha256"])) == (edition["source_key"], edition["reference_date_raw"], edition["document_sha256"])]

    def latest_check(history: dict, edition_id_value: str) -> str | None:
        values = [_time(c["checked_at"]) for c in history["checks"] if c["edition_id"] == edition_id_value]
        return max(values) if values else None

    for after in new["editions"]:
        compatible = [e for e in old_by_scope[scope(after)] if e["parser_signature"] == after["parser_signature"] and e["id"] != after["id"]]
        source_candidates = [e for e in compatible if e["reference_date"] and after["reference_date"] and e["reference_date"] < after["reference_date"]]
        if source_candidates:
            latest = max(e["reference_date"] for e in source_candidates)
            source_candidates = [e for e in source_candidates if e["reference_date"] == latest]
            if len(source_candidates) == 1:
                before = source_candidates[0]
                result["comparisons"].append(compare_rows(rows_for(previous, before), rows_for(current, after), before["id"], after["id"]))
            continue

        # When source chronology is equal or unknown, retain both editions and
        # compare only by successful observation time. This does not assert an
        # administrative/effective chronology. Equal-time payloads are retained
        # but deliberately left unordered.
        after_check = latest_check(new, after["id"])
        if not after_check:
            continue
        observed_candidates: list[tuple[str, dict]] = []
        for candidate in compatible:
            if candidate["reference_date"] and after["reference_date"] and candidate["reference_date"] != after["reference_date"]:
                continue
            candidate_check = latest_check(old, candidate["id"])
            if candidate_check and candidate_check < after_check:
                observed_candidates.append((candidate_check, candidate))
        if not observed_candidates:
            continue
        latest_observation = max(value for value, _ in observed_candidates)
        observed_candidates = [(value, edition) for value, edition in observed_candidates if value == latest_observation]
        if len(observed_candidates) != 1:
            continue
        before = observed_candidates[0][1]
        result["comparisons"].append(compare_rows(rows_for(previous, before), rows_for(current, after), before["id"], after["id"], basis="capture_ordered_identifier_observations_v1"))
    validate_history(result)
    return result


def fetch_previous_public() -> tuple[dict | None, dict | None]:
    """Bounded, optional reuse of our own previously published, approved release.

    No credentials, third-party enrichment or guesses about missing companies.
    A missing previous release disables granular deltas, not current publication.
    """
    payloads = []
    for name in ("history", "registry"):
        try:
            request = Request(f"{PUBLIC_BASE}/data/{name}.json", headers={"User-Agent": "WhiteListArchive-history/1", "Cache-Control": "no-cache"})
            with urlopen(request, timeout=12) as response:
                raw = response.read(120_000_001)
            if len(raw) > 120_000_000:
                raise ValueError("Previous public release exceeds size limit")
            payload = json.loads(raw)
            if name == "history":
                validate_history(payload)
            else:
                from white_list_archive.publishing.public_contract import validate_registry
                validate_registry(payload)
            payloads.append(payload)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            print(f"Optional previous public {name} unavailable ({type(exc).__name__}); no missing comparison is filled with zero.")
            payloads.append(None)
    return payloads[0], payloads[1]


def build_history(registry: dict, ledger: dict, previous_registry: dict | None = None, previous_history: dict | None = None) -> dict:
    current = compare_releases(previous_registry, registry) if previous_registry is not None else aggregate_registry(registry)
    return merge_histories(ledger, previous_history or empty_history(), current)


def write_history(path: Path, history: dict) -> None:
    validate_history(history)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(history, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def publish_history(registry: dict, root: Path, output: Path) -> dict:
    ledger_path = root / "data/history/public_history.json"
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    previous_history, previous_registry = fetch_previous_public()
    history = build_history(registry, ledger, previous_registry, previous_history)
    write_history(output, history)
    return history


def validate_history_registry(history: dict, registry: dict) -> None:
    """Every current approved edition must reconcile with the history export."""
    validate_history(history)
    actual = {e["id"]: e for e in history["editions"]}
    for edition in aggregate_registry(registry)["editions"]:
        old = actual.get(edition["id"])
        if old is None or any(old[k] != edition[k] for k in ("total", "status_counts", "data_fingerprint")):
            raise ValueError("Current registry and history do not reconcile")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--merge", type=Path, required=True)
    args = parser.parse_args()
    old = json.loads(args.ledger.read_text(encoding="utf-8"))
    incoming = json.loads(args.merge.read_text(encoding="utf-8"))
    merged = merge_histories(old, incoming)
    write_history(args.ledger, merged)
    print(f"Validated history: {len(merged['editions'])} editions, {len(merged['checks'])} successful checks, {len(merged['comparisons'])} evidence-backed comparisons.")


if __name__ == "__main__":
    main()
