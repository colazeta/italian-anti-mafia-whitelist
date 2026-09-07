from __future__ import annotations

import argparse
import json
from pathlib import Path


def _load(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return value


ENHANCEMENT_JS = r"""
(()=>{
const TC=window.__TABLE_CATALOG__||{objects:{}};
const SE=window.__SOURCE_EVIDENCE__||{editions:{}};
const esc=window.E||((s)=>String(s??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[m])));
function scalar(v){if(v===null||v===undefined)return '';if(typeof v==='object')return JSON.stringify(v);return String(v)}
function openDataset(code){
 const obj=(TC.objects||{})[code]; if(!obj)return;
 const cols=obj.columns||[], rows=obj.preview_rows||[];
 const head=cols.map(c=>`<th>${esc(c.name)}</th>`).join('');
 const body=rows.map(r=>`<tr>${cols.map(c=>`<td class="mono">${esc(scalar(r[c.name]))}</td>`).join('')}</tr>`).join('');
 const schema=cols.map(c=>`<tr><td class="mono">${esc(c.name)}</td><td>${esc(c.data_type)}</td><td class="mono">${esc(c.udt_name)}</td></tr>`).join('');
 document.querySelector('#detail-title').textContent=`Dataset · ${obj.label}`;
 document.querySelector('#detail-body').innerHTML=`
 <div class="note"><b>${esc(obj.table)}</b> · ${Number(obj.count||0).toLocaleString('it-IT')} righe. Anteprima delle prime ${Number(obj.preview_limit||50)} righe in ordine deterministico.</div>
 <p><a class="btn" style="display:inline-block;text-decoration:none" href="${esc(obj.csv_path)}" target="_blank">Apri CSV completo</a></p>
 <div class="section"><div class="section-title">SCHEMA COLONNE</div><div class="gridwrap"><table class="tree"><thead><tr><th>Colonna</th><th>Tipo SQL</th><th>UDT</th></tr></thead><tbody>${schema}</tbody></table></div></div>
 <div class="section"><div class="section-title">ANTEPRIMA DATI REALI</div><div class="gridwrap"><table class="grid"><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table></div></div>
 <div class="note">Il CSV è un export interno della tabella PostgreSQL ricostruita nello stesso run che ha generato l'Explorer; non è una release pubblica.</div>`;
 document.querySelector('#detail').classList.add('open');
}
function enhanceStructure(){
 const table=document.querySelector('#view-structure table.tree'); if(!table||!D.model_population)return;
 const hr=table.querySelector('thead tr'); if(hr&&!hr.querySelector('.audit-open-head')){const th=document.createElement('th');th.className='audit-open-head';th.textContent='Dati';hr.appendChild(th)}
 const trs=[...table.querySelectorAll('tbody tr')];
 trs.forEach((tr,i)=>{if(tr.querySelector('.audit-open-cell'))return; const o=D.model_population.objects[i]; const td=document.createElement('td');td.className='audit-open-cell'; const b=document.createElement('button');b.className='btn';b.textContent='Apri';b.disabled=!TC.objects?.[o.object_code];b.onclick=(ev)=>{ev.stopPropagation();openDataset(o.object_code)};td.appendChild(b);tr.appendChild(td);tr.style.cursor='pointer';tr.onclick=()=>openDataset(o.object_code)});
 const note=document.createElement('div');note.className='note';note.innerHTML='<b>Le righe della struttura sono ora navigabili.</b> Apri un oggetto per vedere schema, dati reali di esempio e CSV completo.';table.parentElement?.parentElement?.prepend(note);
}
function sourceEditionCard(date){
 const e=(SE.editions||{})[date]; if(!e)return '';
 return `<tr><td>${esc(date)}</td><td>${Number(e.page_count||0).toLocaleString('it-IT')}</td><td class="mono">${esc(e.sha256)}</td><td><a class="btn" style="display:inline-block;text-decoration:none" href="${esc(e.pdf_path)}" target="_blank">PDF originale</a></td><td><a href="${esc(e.resource_url)}" target="_blank" rel="noreferrer">fonte ufficiale</a></td></tr>`
}
function enhanceProvenance(){
 const view=document.querySelector('#view-provenance'); if(!view)return;
 const dates=Object.keys(SE.editions||{}).sort(); if(!dates.length)return;
 const rows=dates.map(sourceEditionCard).join('');
 const box=document.createElement('div');box.className='section';box.innerHTML=`<div class="section-title">ARCHIVIO EVIDENZA — DOCUMENTI ORIGINALI</div><div class="section-body"><div class="note">I PDF originali usati dal parser sono inclusi nel pacchetto di evidenza e verificati contro lo SHA-256 congelato prima del parsing.</div><div class="gridwrap"><table class="tree"><thead><tr><th>Edizione</th><th>Pagine</th><th>SHA-256</th><th>Copia verificata</th><th>Fonte</th></tr></thead><tbody>${rows}</tbody></table></div></div>`;view.prepend(box);
}
const baseOpenDetail=window.openDetail||openDetail;
window.openDetail=openDetail=function(r){
 baseOpenDetail(r);
 const ed=(SE.editions||{})[r.edition]; if(!ed)return;
 const loc=(ed.rows||{})[String(r.row_ordinal)]||{}; const page=loc.page_start;
 const href=ed.pdf_path+(page?`#page=${page}`:'');
 const box=document.createElement('div');box.className='note';box.innerHTML=`<b>Verifica indipendente:</b> <a href="${esc(href)}" target="_blank">apri il PDF originale${page?` a pagina ${page}`:''}</a><br><span class="mono">SHA-256 ${esc(ed.sha256)}</span><br><span class="muted">Locator fisico ricostruito dallo stesso layout a coordinate usato dal parser.</span>`;document.querySelector('#detail-body').prepend(box);
};
enhanceStructure(); enhanceProvenance();
})();
"""


def patch_explorer(index_path: Path, table_catalog: Path, source_evidence: Path) -> None:
    html = index_path.read_text(encoding="utf-8")
    if "__AUDIT_DRILLDOWN_V1__" in html:
        raise ValueError("Explorer already contains audit drilldown patch")
    table_payload = _load(table_catalog)
    evidence_payload = _load(source_evidence)
    injection = (
        "\n<!-- __AUDIT_DRILLDOWN_V1__ -->\n<script>"
        "window.__TABLE_CATALOG__=" + json.dumps(table_payload, ensure_ascii=False, separators=(",", ":")) + ";"
        "window.__SOURCE_EVIDENCE__=" + json.dumps(evidence_payload, ensure_ascii=False, separators=(",", ":")) + ";"
        "</script>\n<script>" + ENHANCEMENT_JS + "</script>\n"
    )
    if "</body>" not in html:
        raise ValueError("Explorer HTML has no closing body tag")
    index_path.write_text(html.replace("</body>", injection + "</body>"), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Add database drilldown and original-source evidence controls to a generated Dataset Explorer.")
    parser.add_argument("--index", type=Path, required=True)
    parser.add_argument("--table-catalog", type=Path, required=True)
    parser.add_argument("--source-evidence", type=Path, required=True)
    args = parser.parse_args()
    patch_explorer(args.index, args.table_catalog, args.source_evidence)
    print(json.dumps({"patched": str(args.index)}, indent=2))


if __name__ == "__main__":
    main()
