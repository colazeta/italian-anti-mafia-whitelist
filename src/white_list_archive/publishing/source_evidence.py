from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

from white_list_archive.parsers.cosenza_combined_v2 import _bbox_words, _is_row_start, _lines


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _row_pages(pdf: Path) -> dict[str, dict[str, int]]:
    lines = _lines(_bbox_words(pdf))
    starts = [index for index, line in enumerate(lines) if _is_row_start(line)]
    output: dict[str, dict[str, int]] = {}
    for ordinal, start in enumerate(starts, start=1):
        # The parser's row start is a stable physical locator. Page start is enough
        # to take an independent reviewer directly to the source evidence, without
        # pretending that the row's visual extent is perfectly delimited.
        output[str(ordinal)] = {"page_start": int(lines[start]["page"])}
    return output


def _load_manifest(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return value


def _edition(pdf: Path, manifest_path: Path, target: Path) -> dict[str, Any]:
    manifest = _load_manifest(manifest_path)
    observed_sha = _sha256(pdf)
    if observed_sha != manifest["sha256"]:
        raise ValueError(
            f"Source evidence bytes do not match frozen manifest for {manifest.get('reference_date')}: "
            f"{observed_sha} != {manifest['sha256']}"
        )
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(pdf, target)
    return {
        "reference_date": manifest["reference_date"],
        "pdf_path": target.as_posix(),
        "sha256": observed_sha,
        "byte_size": pdf.stat().st_size,
        "page_count": manifest["page_count"],
        "resource_url": manifest["resource_url"],
        "source_page_url": manifest.get("page_url"),
        "rows": _row_pages(pdf),
    }


def build_evidence(
    before_pdf: Path,
    after_pdf: Path,
    before_manifest: Path,
    after_manifest: Path,
    output_dir: Path,
) -> dict[str, Any]:
    source_dir = output_dir / "source-documents" / "cosenza"
    before_meta = _load_manifest(before_manifest)
    after_meta = _load_manifest(after_manifest)
    editions = {}
    for pdf, manifest_path, meta in (
        (before_pdf, before_manifest, before_meta),
        (after_pdf, after_manifest, after_meta),
    ):
        reference_date = str(meta["reference_date"])
        target = source_dir / f"{reference_date}.pdf"
        item = _edition(pdf, manifest_path, target)
        # Paths consumed by the HTML must be relative to the Explorer root.
        item["pdf_path"] = f"source-documents/cosenza/{reference_date}.pdf"
        editions[reference_date] = item
    return {
        "archive_policy": "Explorer evidence package copy; content identity fixed by SHA-256. Production durable storage remains a separate storage backend.",
        "editions": editions,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Package original source PDFs and row-to-page locators for independent parser review.")
    parser.add_argument("--before-pdf", type=Path, required=True)
    parser.add_argument("--after-pdf", type=Path, required=True)
    parser.add_argument("--before-manifest", type=Path, required=True)
    parser.add_argument("--after-manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    payload = build_evidence(
        args.before_pdf,
        args.after_pdf,
        args.before_manifest,
        args.after_manifest,
        args.output_dir,
    )
    json_path = args.output_dir / "source_evidence.json"
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    js_path = args.output_dir / "source_evidence.js"
    js_path.write_text(
        "window.__SOURCE_EVIDENCE__=" + json.dumps(payload, ensure_ascii=False) + ";\n",
        encoding="utf-8",
    )
    print(json.dumps({"output": str(json_path), "javascript": str(js_path), "editions": len(payload["editions"])}, indent=2))


if __name__ == "__main__":
    main()
