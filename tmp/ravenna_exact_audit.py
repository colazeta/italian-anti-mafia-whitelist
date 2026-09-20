import json, re
from collections import Counter
from datetime import datetime
from pathlib import Path

pages = json.loads(Path('tmp/ravenna-extracted-tables.json').read_text(encoding='utf-8'))
source = json.loads(Path('tmp/ravenna-source-probe.json').read_text(encoding='utf-8'))
header = ['N. prog.','Ragione sociale e p. iva / cf','Indirizzo sede legale','DATA PRIMA RICHIESTA','DATA ISCRIZIONE/ RINNOVO','NOTE','sez. I','sez.II','sez. III','sez. IV','sez. V','sez. VI','sez. VII','sez. VIII','sez. IX','sez. X']
rows=[]; page_rows=[]
for p in pages:
    assert len(p['tables']) == 1, p['page']
    table=p['tables'][0]
    assert table[0] == header, (p['page'], table[0])
    body=table[1:]; page_rows.append(len(body))
    for row in body:
        assert len(row) == 16
        rows.append((p['page'], row))
assert len(rows) == 706

statuses=Counter(); notes=Counter(); section_cells=Counter(); malformed_dates=[]
blank_names=[]; blank_addresses=[]; bad_prog=[]; prog=Counter(); identifier_rows=0; no_identifier=[]
vat=re.compile(r'(?<!\d)\d{11}(?!\d)')
cf=re.compile(r'(?<![A-Z0-9])[A-Z0-9]{16}(?![A-Z0-9])', re.I)

def check_date(raw, page, ordinal, field):
    if not raw: return
    try: datetime.strptime(raw, '%d/%m/%Y')
    except ValueError: malformed_dates.append({'page':page,'ordinal':ordinal,'field':field,'raw':raw})

for ordinal,(page,row) in enumerate(rows,1):
    n,company,address,application,listing,note,*sections = [x.strip() for x in row]
    if n.isdigit(): prog[n]+=1
    else: bad_prog.append({'page':page,'ordinal':ordinal,'raw':n})
    if not company: blank_names.append({'page':page,'ordinal':ordinal,'prog':n})
    if not address: blank_addresses.append({'page':page,'ordinal':ordinal,'prog':n})
    check_date(application,page,ordinal,'application'); check_date(listing,page,ordinal,'listing')
    notes[note]+=1
    for cell in sections: section_cells[cell]+=1
    if note == 'Richiesto rinnovo - Aggiornamento in corso': status='renewal_update_in_progress'
    elif note: status='other_or_unknown'
    elif listing: status='listed'
    elif application: status='pending'
    else: status='other_or_unknown'
    statuses[status]+=1
    ids=[]
    for token in vat.findall(company.upper()) + cf.findall(company.upper()):
        if token not in ids: ids.append(token)
    if ids: identifier_rows+=1
    else: no_identifier.append({'page':page,'ordinal':ordinal,'prog':n,'company_raw':company})

receipt={
 'source_url':source['selected_attachment']['url'],
 'source_sha256':source['independent_pdf_fetches'][0]['sha256'],
 'source_bytes':source['independent_pdf_fetches'][0]['bytes'],
 'pages':len(pages),'page_rows':page_rows,'records':len(rows),
 'status_counts':dict(statuses),'note_counts':dict(notes),'section_cell_counts':dict(section_cells),
 'identifier_row_coverage':identifier_rows,'rows_without_structured_identifier':len(no_identifier),
 'rows_without_structured_identifier_examples':no_identifier[:50],
 'malformed_dates':malformed_dates,'blank_name_rows':blank_names,'blank_address_rows':blank_addresses,
 'nonnumeric_progressive_rows':bad_prog,'duplicate_progressive_values':{k:v for k,v in prog.items() if v != 1},
}
Path('tmp/ravenna-exact-audit.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(receipt,ensure_ascii=False,indent=2))
