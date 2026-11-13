"""Exact October Alessandria source QA; only aggregate data and header images leave runner."""
from collections import Counter
from pathlib import Path
import hashlib
import json
import os
import re
import tempfile

import pdfplumber
from white_list_archive.parsers.multi_prefecture_tables import (
    _clean, _AL_YEAR, _DMY_FLEX,
)
from white_list_archive.parsers.alessandria_october import PARSERS
from white_list_archive.publishing.public_national_registry import _download
from white_list_archive.publishing.public_contract import public_record

PINS = {
    'listed': ('https://prefettura.interno.gov.it/sites/default/files/14/2026-10/white-list-28-ottobre-2026.pdf',
               '7081de5f4bd1a583abc2a9024396857db3717e2ed6d1ad0f5a4d6e30dc7152cf', 1296335),
    'applicants': ('https://prefettura.interno.gov.it/sites/default/files/14/2026-10/elenco-imprese-richiedenti-iscrizione-in-white-list-28-ottobre-2026.pdf',
                   'b10733818c5e7f04b40c3b7d76da837acbe12e300e2d2e9b79f249bd48837b34', 161221),
}


def main():
    config = json.loads(Path('data/publication/multi_prefecture_pilot.json').read_text())
    output = Path(os.environ.get('ALESSANDRIA_QA_DIR', '/tmp/alessandria-source-qa'))
    output.mkdir(parents=True, exist_ok=True)
    results = []
    with tempfile.TemporaryDirectory(prefix='alessandria-source-only-') as td:
        for label, (url, sha, size) in PINS.items():
            cfg = next(s for s in config['sources'] if s['source_key'] == 'alessandria-' + label)
            cfg = {**cfg, 'sha256': sha, 'resource_url': url, 'reference_date': '2026-10-28'}
            path = Path(td) / (label + '.pdf')
            if _download(url, path) != sha or path.stat().st_size != size:
                raise RuntimeError('Alessandria original identity mismatch')
            physical = 0; widths = Counter(); masks = Counter(); candidates = 0
            no_tables = []; header_coords = []; sections = []; data_digest = hashlib.sha256()
            with pdfplumber.open(path) as pdf:
                pages = len(pdf.pages)
                dated_title = bool(re.search(r'28\s+(?:ottobre|OTTOBRE)\s+2026', pdf.pages[0].extract_text() or ''))
                for pno, page in enumerate(pdf.pages, 1):
                    tables = page.find_tables()
                    if not tables: no_tables.append(pno)
                    for tno, table in enumerate(tables, 1):
                        for rno, raw in enumerate(table.extract() or [], 1):
                            c = [_clean(v) for v in raw]; physical += 1; widths[len(c)] += 1
                            masks[''.join('1' if v else '0' for v in c)] += 1
                            data_digest.update(json.dumps([pno,tno,rno,c], ensure_ascii=False,separators=(',',':')).encode())
                            if c and c[0].upper().startswith('SEZIONE'):
                                sections.append(c[0])
                            if any('RAGIONE' in v.upper() or 'CODICE FISCALE' in v.upper() for v in c):
                                header_coords.append([pno,tno,rno])
                            # Independent identity-bearing row census, including rows without dates.
                            index = 3 if label == 'listed' else 2
                            if len(c)>index and c[0] and len(re.sub(r'[^A-Za-z0-9]','',c[index])) >= 8 and re.search(r'\d',c[index]):
                                candidates += 1
                    if pno == 1:
                        # Exact pinned documents: the reviewed column-heading row is
                        # r10 (listed) / r2 (applicants), before any company record.
                        first_table = tables[0]
                        header_index = 9 if label == 'listed' else 1
                        header_cells = [_clean(v) for v in first_table.extract()[header_index]]
                        if not any('RAGIONE' in v.upper() for v in header_cells):
                            raise RuntimeError('Alessandria safe-header boundary drift')
                        top = first_table.rows[header_index].bbox[3]
                        page.crop((0,0,page.width,top)).to_image(resolution=130).save(output/(label+'-headers.png'))
            batch = PARSERS[cfg['parser']](path, cfg)
            for row in batch.records: public_record(row)
            diagnostics = batch.diagnostics
            if not batch.records or diagnostics.get('dropped_date_rows'):
                raise RuntimeError('Alessandria empty output or dropped source rows')
            result = {'source_key':cfg['source_key'],'source_sha256':sha,'source_bytes':size,
                      'pages':pages,'physical_rows':physical,'row_widths':dict(widths),
                      'row_masks':dict(masks),'identity_bearing_rows':candidates,
                      'no_table_pages':no_tables,'table_header_coordinates':header_coords,
                      'dated_title_matches_28_october':dated_title,
                      'sections':sorted(set(sections)),'all_physical_rows_digest':data_digest.hexdigest(),
                      'parser_diagnostics':diagnostics,'publication_performed':False}
            results.append(result)
    (output/'aggregate-qa.json').write_text(json.dumps(results, ensure_ascii=False,indent=2))
    print(json.dumps({'mode':'source_only_not_publication','sources':results},ensure_ascii=False,sort_keys=True))


if __name__ == '__main__': main()
