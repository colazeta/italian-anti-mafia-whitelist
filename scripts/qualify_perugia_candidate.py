"""Review-only, safe aggregate Perugia parser qualification.

No publication, DB writes, new source approvals or output of source rows.
The temporary revision/SHA override below is deliberately local to this
preflight process; strict production parsers remain unchanged/fail-closed.
"""
from __future__ import annotations

import json
import os
import shutil
import re
from collections import Counter
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
            evidence_dir = os.environ.get('PERUGIA_REVIEW_EVIDENCE_DIR')
            if evidence_dir:
                target = Path(evidence_dir)
                target.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(path, target / f'{source_key}.pdf')
            with pdfplumber.open(path) as pdf:
                page_count=len(pdf.pages)
                # Profile every physical page without logging table cells.
                # These are review-only aggregates, not parser acceptance rules.
                page_sizes=sorted(set((round(p.width),round(p.height)) for p in pdf.pages))
                table_counts=Counter()
                width_counts=Counter()
                row_masks=Counter()
                status_categories=Counter()
                date_shapes=Counter()
                missing_first_column=[]
                header_coords=[]
                unusual_status_coords=[]
                unusual_date_coords=[]
                zero_table_pages=[]
                multi_table_pages=[]
                physical_rows=0
                page_row_counts={}
                for pno,page in enumerate(pdf.pages,1):
                    tables=page.find_tables()
                    table_counts[len(tables)]+=1
                    if not tables:
                        zero_table_pages.append(pno)
                    elif len(tables)>1:
                        multi_table_pages.append(pno)
                    for table in tables:
                        rows=table.extract() or []
                        page_row_counts[pno]=page_row_counts.get(pno,0)+len(rows)
                        physical_rows+=len(rows)
                        for rno,row in enumerate(rows,1):
                            width_counts[len(row)]+=1
                            cells=[parser._clean(v) for v in row]
                            if len(cells)!=7:
                                continue
                            mask=''.join('1' if v else '0' for v in cells)
                            row_masks[mask]+=1
                            if cells[0]=='Ragione Sociale':
                                header_coords.append([pno,rno])
                                continue
                            if not cells[0] and any(cells):
                                missing_first_column.append([pno,rno,mask])
                            if not any(cells):
                                continue
                            c6=cells[6]
                            if label=='listed':
                                kind='SI' if c6=='SI' else 'blank' if not c6 else 'other'
                            else:
                                kind='blank' if not c6 else next(
                                    (part for part in ('rinnovo','iscritta','iscrizione')
                                     if c6.casefold().startswith(part)), 'other')
                            status_categories[kind]+=1
                            if kind=='other':
                                unusual_status_coords.append([pno,rno])
                            for col in (4,5):
                                value=cells[col]
                                if not value:
                                    date_shapes[f'column_{col}_blank']+=1
                                elif re.fullmatch(r'\d{1,2}[./]\d{1,2}[./]\d{4}', value):
                                    date_shapes[f'column_{col}_calendar_like']+=1
                                else:
                                    date_shapes[f'column_{col}_other']+=1
                                    if len(unusual_date_coords)<40:
                                        unusual_date_coords.append([pno,rno,col])
                if label=='listed':
                    legacy_continuations=list(parser._LISTED_CONTINUATIONS)
                else:
                    legacy_continuations=list(parser._APPLICANT_CONTINUATIONS)
                legacy_continuations=[list(x) for x in sorted(legacy_continuations)]
                by_tens={}
                for pno,count in page_row_counts.items():
                    group=f'{((pno-1)//10)*10+1}-{((pno-1)//10)*10+10}'
                    by_tens[group]=by_tens.get(group,0)+count
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
                'page_sizes_pt':page_sizes,
                'pages_by_table_count':dict(sorted(table_counts.items())),
                'zero_table_pages':zero_table_pages[:25],
                'more_than_25_zero_table_pages':len(zero_table_pages)>25,
                'multi_table_pages':multi_table_pages[:25],
                'observed_table_rows':physical_rows,
                'extracted_row_widths':dict(sorted(width_counts.items())),
                'header_coords':header_coords,
                'nonempty_row_masks':dict(sorted(row_masks.items())),
                'rows_missing_name_count':len(missing_first_column),
                'rows_missing_name_coords':missing_first_column[:80],
                'legacy_continuation_coords':legacy_continuations,
                'status_categories':dict(sorted(status_categories.items())),
                'unusual_status_coords':unusual_status_coords[:50],
                'date_shapes':dict(sorted(date_shapes.items())),
                'unusual_date_coords':unusual_date_coords,
                'page_rows_by_ten':by_tens,
                'release_approved':False,
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
