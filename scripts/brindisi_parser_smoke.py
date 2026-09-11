from __future__ import annotations
import hashlib,json,os,urllib.request
from pathlib import Path
from white_list_archive.parsers.brindisi_tables import parse_brindisi_applicants,parse_brindisi_listed
from white_list_archive.publishing.public_national_registry import _semantic_digest

def fetch(url,path):
    req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 white-list-archive-parser-smoke'})
    with urllib.request.urlopen(req,timeout=60) as response: body=response.read()
    if not body.startswith(b'%PDF'): raise RuntimeError(f'not a PDF: {url}')
    path.write_bytes(body); return hashlib.sha256(body).hexdigest()

def config(key,scope,url,sha):
    return {'source_key':key,'authority_key':'brindisi','authority_name':'Prefettura di Brindisi','register_key':'brindisi-ordinary','register_name':'White List ordinaria','population_scope':scope,'reference_date':'2026-09-08','source_page_url':'https://prefettura.interno.gov.it/it/prefetture/brindisi/evidenza/white-list','resource_url':url,'sha256':sha}

def check(kind,url,parser):
    digests=[]
    for capture in (1,2):
        path=Path(f'/tmp/brindisi-{kind}-{capture}.pdf'); raw=fetch(url,path)
        batch=parser(path,config(f'brindisi-{kind}','listed' if kind=='listed' else 'applicant',url,raw))
        semantic=_semantic_digest(batch.records); digests.append(semantic)
        print('SMOKE',kind,capture,raw,semantic,json.dumps(batch.diagnostics,ensure_ascii=False,sort_keys=True))
        if kind=='applicants': print('APPLICANTS',json.dumps(batch.records,ensure_ascii=False))
    if len(set(digests))!=1: raise RuntimeError(f'{kind}: semantic drift across captures: {digests}')

def main():
    check('listed',os.environ['LISTED_URL'],parse_brindisi_listed)
    check('applicants',os.environ['APPLICANT_URL'],parse_brindisi_applicants)
if __name__=='__main__': main()
