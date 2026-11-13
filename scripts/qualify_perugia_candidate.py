"""Review-only, safe aggregate Perugia parser qualification.

No publication, DB writes, new source approvals or output of source rows.
The temporary revision/SHA override below is deliberately local to this
preflight process; strict production parsers remain unchanged/fail-closed.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
import tempfile
import pdfplumber
from white_list_archive.publishing.public_national_registry import _download
from white_list_archive.parsers import perugia_tables as parser


def category(error: BaseException) -> str:
    message = str(error).casefold()
    for token, label in [
        ("page-count drift", "page_count_drift"),
        ("physical", "physical_layout_drift"),
        ("section", "section_layout_drift"),
        ("table", "table_layout_drift"),
        ("continuation", "continuation_drift"),
        ("source-row", "source_row_drift"),
        ("source row", "source_row_drift"),
        ("expected", "expected_count_drift"),
        ("date", "source_date_review"),
        ("identifier", "identifier_review"),
        ("status", "status_review"),
        ("hash", "byte_integrity"),
    ]:
        if token in message:
            return label
    return "other_strict_parser_review"


def main() -> None:
    config=json.loads(Path('data/publication/multi_prefecture_pilot.json').read_text())
    sources={s['source_key']:s for s in config['sources']}
    results=[]
    with tempfile.TemporaryDirectory(prefix='perugia-source-qa-') as td:
        for source_key, label in [('perugia-listed','listed'),('perugia-applicants','applicants')]:
            cfg=sources[source_key]
            if cfg.get('reference_date') != '2026-11-05':
                raise SystemExit('Candidate qualification requires explicit November 2026 Perugia source dates')
            path=Path(td)/f'{source_key}.pdf'
            digest=_download(cfg['resource_url'],path)
            if digest!=cfg['sha256']:
                raise SystemExit(f'{source_key}: candidate source SHA mismatch; no review performed')
            with pdfplumber.open(path) as pdf:
                page_count=len(pdf.pages)
                # Aggregate physical-document metadata only: no extracted rows,
                # names, source text or private capture provenance in artifacts.
                page_sizes=sorted(set((round(p.width),round(p.height)) for p in pdf.pages))
            parser._REFERENCE_DATE=cfg['reference_date']
            if label=='listed':
                parser._LISTED_SHA256=cfg['sha256']
                expected_pages=parser._LISTED_PAGES
                run=parser.parse_perugia_listed
            else:
                parser._APPLICANT_SHA256=cfg['sha256']
                expected_pages=parser._APPLICANT_PAGES
                run=parser.parse_perugia_applicants
            result={
                'source_key':source_key, 'official_candidate_date':cfg['reference_date'],
                'raw_sha256_verified':True,'physical_pages':page_count,
                'legacy_expected_pages':expected_pages,
                'page_sizes_pt':page_sizes, 'release_approved':False,
            }
            try:
                batch=run(path,cfg)
            except Exception as exc:
                result.update(strict_legacy_parser='quarantined',
                              issue_category=category(exc),
                              error_class=type(exc).__name__)
                if page_count != expected_pages:
                    # Diagnostic pass only: override the one observed physical
                    # page count to expose the NEXT fail-closed parser invariant.
                    # The shipping parser stays byte-for-byte unchanged.
                    if label == 'listed':
                        parser._LISTED_PAGES=page_count
                    else:
                        parser._APPLICANT_PAGES=page_count
                    try:
                        deeper=run(path,cfg)
                    except Exception as deeper_exc:
                        result.update(next_parser_gate=category(deeper_exc),
                                      next_error_class=type(deeper_exc).__name__)
                        # A numeric page count is a harmless diagnostic; never
                        # emit source rows, names or exception text.
                        match=re.search(r'table-count drift on page (\d+): (\d+) != (\d+)',str(deeper_exc))
                        if match:
                            result.update(first_changed_table_page=int(match.group(1)),
                                          observed_tables_on_page=int(match.group(2)),
                                          legacy_expected_tables=int(match.group(3)))
                    else:
                        result.update(next_parser_gate='all_remaining_legacy_gates_passed',
                                      probe_observations=len(deeper.records))
            else:
                result.update(strict_legacy_parser='compatible',
                              observations=len(batch.records),
                              diagnostics={k:v for k,v in batch.diagnostics.items()
                                   if isinstance(v,(str,int,float,bool,type(None)))
                                   and k not in ('source', 'rows', 'names')})
            results.append(result)
    print(json.dumps({'mode':'source_only_not_for_publication','results':results},
                     ensure_ascii=False,sort_keys=True))


if __name__=='__main__':
    main()
