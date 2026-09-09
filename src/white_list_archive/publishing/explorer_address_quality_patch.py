from __future__ import annotations

import argparse
import csv
import html
import json
from collections import Counter
from pathlib import Path
from typing import Any

TAB_MARKER = '<button class="tab" data-view="method">Metodo</button>'
VIEW_MARKER = '<section class="view" id="view-method"></section>'
STYLE_MARKER = '</style>'
BODY_MARKER = '</body>'
MATCHED_STATUSES = {"accepted", "candidate"}


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return value


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _pct(numerator: int, denominator: int) -> float | None:
    if not denominator:
        return None
    return round(100.0 * numerator / denominator, 2)


def _normalised_counts(values: dict[str, Any]) -> dict[str, int]:
    return {str(key): int(value) for key, value in values.items() if int(value) != 0}


def build_quality_payload(
    *,
    summary_path: Path,
    address_results_path: Path,
    frozen_review_summary_path: Path,
    frozen_review_metadata_path: Path,
    address_results_href: str,
) -> dict[str, Any]:
    summary = _load_json(summary_path)
    rows = _read_csv(address_results_path)
    frozen_summary = _load_json(frozen_review_summary_path)
    frozen_metadata = _load_json(frozen_review_metadata_path)

    total = len(rows)
    expected_total = int(summary.get("total_canonical_addresses", -1))
    if total != expected_total:
        raise ValueError(
            f"Address-results rows ({total}) do not match validation summary ({expected_total})"
        )

    status_counts = Counter(
        ((row.get("match_status") or "unprocessed").strip() or "unprocessed")
        for row in rows
    )
    observed_status = _normalised_counts(dict(status_counts))
    expected_status = _normalised_counts(summary.get("status_counts") or {})
    if observed_status != expected_status:
        raise ValueError(
            f"Address status counts do not reconcile: observed={observed_status}, expected={expected_status}"
        )

    matched_rows = [
        row for row in rows if (row.get("match_status") or "").strip() in MATCHED_STATUSES
    ]
    matched = len(matched_rows)
    if matched != int(summary.get("addresses_with_provider_match", -1)):
        raise ValueError("Matched-address count does not reconcile with validation summary")

    precision_counts = Counter(
        ((row.get("precision_code") or "unknown").strip() or "unknown")
        for row in matched_rows
    )
    expected_precision = _normalised_counts(summary.get("precision_counts") or {})
    observed_precision = _normalised_counts(dict(precision_counts))
    if observed_precision != expected_precision:
        raise ValueError(
            f"Precision counts do not reconcile: observed={observed_precision}, expected={expected_precision}"
        )

    accepted = status_counts.get("accepted", 0)
    candidate = status_counts.get("candidate", 0)
    not_found = status_counts.get("not_found", 0)
    errors = status_counts.get("error", 0)
    unprocessed = status_counts.get("unprocessed", 0)
    accounted = accepted + candidate + not_found + errors + unprocessed
    attempted = total - unprocessed
    if accounted != total:
        raise ValueError(f"Address operational accounting is incomplete: {accounted} != {total}")

    coordinate_bearing = sum(
        bool((row.get("latitude") or "").strip())
        and bool((row.get("longitude") or "").strip())
        for row in matched_rows
    )
    normalisation_only = matched - coordinate_bearing

    provider_records = sorted(
        {
            (
                (row.get("provider_name") or "").strip(),
                (row.get("provider_version") or "").strip(),
                (row.get("provider_data_updated") or "").strip(),
                (row.get("provider_endpoint") or "").strip(),
            )
            for row in rows
            if (row.get("provider_name") or "").strip()
        }
    )
    providers = [
        {
            "provider_name": name,
            "provider_version": version,
            "provider_data_updated": updated,
            "provider_endpoint": endpoint,
        }
        for name, version, updated, endpoint in provider_records
    ]

    review_population = int(frozen_summary.get("population", -1))
    if review_population != total:
        raise ValueError(
            f"Frozen review population ({review_population}) does not match current validation population ({total})"
        )
    if int(frozen_metadata.get("population", -1)) != review_population:
        raise ValueError("Frozen review metadata and summary populations disagree")

    strata = frozen_summary.get("strata") or {}
    review_strata: list[dict[str, Any]] = []
    for key in (
        "matched_civic_access",
        "matched_street",
        "matched_without_coordinates",
        "not_found",
    ):
        value = strata.get(key)
        if not isinstance(value, dict):
            continue
        review_strata.append(
            {
                "stratum": key,
                "population": int(value.get("population", 0)),
                "sample": int(value.get("sample", 0)),
                "correct": int(value.get("correct", 0)),
                "incorrect": int(value.get("incorrect", 0)),
                "review_completion_pct": value.get("review_completion_pct"),
                "determinate_precision_pct": value.get("determinate_precision_pct"),
                "is_candidate_stratum": bool(value.get("is_candidate_stratum")),
            }
        )

    return {
        "schema_version": 1,
        "operational": {
            "generated_at": summary.get("generated_at"),
            "provider_filter": summary.get("provider_filter"),
            "provider_endpoint_filter": summary.get("provider_endpoint_filter"),
            "total_canonical_addresses": total,
            "attempted": attempted,
            "accounted": accounted,
            "matched": matched,
            "candidate": candidate,
            "accepted": accepted,
            "not_found": not_found,
            "errors": errors,
            "unprocessed": unprocessed,
            "match_rate_pct": _pct(matched, total),
            "coordinate_bearing": coordinate_bearing,
            "normalisation_only": normalisation_only,
            "precision_counts": dict(sorted(precision_counts.items())),
            "providers": providers,
        },
        "frozen_review": {
            "review_name": frozen_metadata.get("review_name"),
            "review_date": frozen_metadata.get("review_date"),
            "sample_fingerprint": frozen_metadata.get("sample_fingerprint"),
            "review_file": frozen_metadata.get("versioned_decision_file"),
            "candidate_population": int(frozen_summary.get("candidate_population", 0)),
            "candidate_coverage_pct": frozen_summary.get("candidate_coverage_pct"),
            "candidate_weighted_precision_pct": frozen_summary.get(
                "candidate_weighted_precision_pct"
            ),
            "estimated_validated_yield_pct": frozen_summary.get(
                "estimated_validated_yield_pct"
            ),
            "not_found_population": int(frozen_summary.get("not_found_population", 0)),
            "precision_excludes_not_found": bool(
                frozen_summary.get("precision_excludes_not_found")
            ),
            "strata": review_strata,
        },
        "drilldown": {
            "address_results_href": address_results_href,
            "address_results_rows": total,
        },
    }


def _fmt_number(value: Any) -> str:
    if value is None:
        return "—"
    if isinstance(value, float):
        return f"{value:.2f}".rstrip("0").rstrip(".")
    return str(value)


def _esc(value: Any) -> str:
    return html.escape(str(value if value is not None else "—"), quote=True)


def _section(title: str, body: str) -> str:
    return (
        '<div class="section"><div class="section-title">'
        + _esc(title)
        + '</div><div class="section-body">'
        + body
        + "</div></div>"
    )


def _render_quality_html(payload: dict[str, Any]) -> str:
    op = payload["operational"]
    review = payload["frozen_review"]
    drill = payload["drilldown"]

    accounting_rows = [
        ("Popolazione canonica", op["total_canonical_addresses"], "core.address nel run ricostruito"),
        ("Tentati", op["attempted"], "popolazione meno unprocessed"),
        ("Contabilizzati", op["accounted"], "candidate + accepted + not_found + error + unprocessed"),
        ("Candidate", op["candidate"], "risultato provider; non è geografia accettata"),
        ("Accepted", op["accepted"], "stato di produzione, distinto dalla precisione empirica"),
        ("Not found", op["not_found"], "fallimento di copertura/recall"),
        ("Error", op["errors"], "errore provider/runtime"),
        ("Unprocessed", op["unprocessed"], "nessun tentativo nel run"),
        ("Con coordinate", op["coordinate_bearing"], "candidate/accepted con latitudine e longitudine"),
        ("Solo normalizzazione", op["normalisation_only"], "match senza coppia di coordinate"),
    ]
    accounting = "".join(
        f"<tr><td>{_esc(label)}</td><td class=\"mono\">{_esc(value)}</td><td>{_esc(note)}</td></tr>"
        for label, value, note in accounting_rows
    )

    provider_rows = op.get("providers") or []
    if provider_rows:
        providers = "".join(
            "<tr>"
            f"<td>{_esc(item.get('provider_name'))}</td>"
            f"<td class=\"mono\">{_esc(item.get('provider_version') or '—')}</td>"
            f"<td>{_esc(item.get('provider_data_updated') or '—')}</td>"
            f"<td class=\"mono\">{_esc(item.get('provider_endpoint') or '—')}</td>"
            "</tr>"
            for item in provider_rows
        )
    else:
        providers = '<tr><td colspan="4" class="muted">Nessuna provenance provider presente.</td></tr>'

    precision = "".join(
        f"<tr><td class=\"mono\">{_esc(key)}</td><td>{_esc(value)}</td></tr>"
        for key, value in sorted((op.get("precision_counts") or {}).items())
    )

    review_rows = "".join(
        "<tr>"
        f"<td class=\"mono\">{_esc(item['stratum'])}</td>"
        f"<td>{_esc(item['population'])}</td>"
        f"<td>{_esc(item['sample'])}</td>"
        f"<td>{_esc(item['correct'])}</td>"
        f"<td>{_esc(item['incorrect'])}</td>"
        f"<td>{_esc(_fmt_number(item['determinate_precision_pct']))}{'%' if item['determinate_precision_pct'] is not None else ''}</td>"
        "</tr>"
        for item in review.get("strata", [])
    )

    production_state = (
        '<span class="status POPULATED">0 accepted · candidate-by-default</span>'
        if op["accepted"] == 0
        else f'<span class="status REQUIRES_REVIEW">{_esc(op["accepted"])} accepted · verificare policy di promozione</span>'
    )

    body = _section(
        "QUALITÀ NORMALIZZAZIONE INDIRIZZI — STATO OPERATIVO",
        '<div class="note"><b>Contabilità source-backed del run corrente.</b> '
        "Le stime di precisione empirica riportate più sotto non modificano lo stato di produzione. "
        f"Stato produzione: {production_state}</div>"
        '<table class="summary"><thead><tr><th>Indicatore</th><th>N.</th><th>Interpretazione</th></tr></thead>'
        f"<tbody>{accounting}</tbody></table>"
        f'<div class="aq-reconcile">Riconciliazione: <b>{_esc(op["accounted"])}/{_esc(op["total_canonical_addresses"])}</b> indirizzi contabilizzati · match rate <b>{_esc(_fmt_number(op["match_rate_pct"]))}%</b>.</div>',
    )
    body += _section(
        "PROVIDER / VERSIONE / RUN PROVENANCE",
        '<table class="summary"><thead><tr><th>Provider</th><th>Versione</th><th>Dati aggiornati</th><th>Endpoint/input</th></tr></thead>'
        f"<tbody>{providers}</tbody></table>"
        f'<div class="aq-provenance">Validation summary generated_at: <span class="mono">{_esc(op.get("generated_at") or "—")}</span> · provider filter: <span class="mono">{_esc(op.get("provider_filter") or "—")}</span>.</div>',
    )
    body += _section(
        "CLASSI OPERATIVE DEL RISULTATO PROVIDER",
        '<div class="split"><div><table class="summary"><thead><tr><th>Precision code</th><th>N.</th></tr></thead>'
        f"<tbody>{precision}</tbody></table></div>"
        '<div><table class="summary"><tr><th>Con coordinate</th><td>'
        f'{_esc(op["coordinate_bearing"])}</td></tr><tr><th>Solo normalizzazione</th><td>{_esc(op["normalisation_only"])}</td></tr>'
        f'<tr><th>Matched totali</th><td>{_esc(op["matched"])}</td></tr></table></div></div>',
    )
    body += _section(
        "GOLD STANDARD CONGELATO — EVIDENZA EMPIRICA",
        '<div class="note"><b>Questi valori sono stime da revisione sostanziale, non stati di produzione.</b> '
        f'{_esc(review.get("review_name") or "Review")}, data {_esc(review.get("review_date") or "—")}, fingerprint <span class="mono">{_esc((review.get("sample_fingerprint") or "")[:16])}…</span>.</div>'
        '<table class="summary"><tr><th>Candidate coverage</th><td>'
        f'{_esc(_fmt_number(review.get("candidate_coverage_pct")))}%</td><th>Candidate precision pesata</th><td>{_esc(_fmt_number(review.get("candidate_weighted_precision_pct")))}%</td><th>Yield end-to-end stimato</th><td>{_esc(_fmt_number(review.get("estimated_validated_yield_pct")))}%</td></tr></table>'
        '<div class="gridwrap"><table class="tree"><thead><tr><th>Strato</th><th>Popolazione</th><th>Campione</th><th>Corretti</th><th>Errati</th><th>Precisione determinata</th></tr></thead>'
        f"<tbody>{review_rows}</tbody></table></div>"
        f'<div class="aq-provenance">Decision file: <span class="mono">{_esc(review.get("review_file") or "—")}</span> · not_found esclusi dal denominatore di precisione: <b>{_esc(review.get("precision_excludes_not_found"))}</b>.</div>',
    )
    body += _section(
        "DRILL-DOWN / AUDIT",
        '<div class="note">Gli aggregati devono poter essere ricondotti alle righe. '
        f'<a href="{_esc(drill["address_results_href"])}" target="_blank" rel="noopener">Apri address_results.csv completo ({_esc(drill["address_results_rows"])} righe)</a>. '
        '<button class="btn" id="aq-open-review" type="button">Apri Validazione indirizzi</button></div>',
    )
    return body


CSS = r'''
.aq-reconcile,.aq-provenance{margin-top:4px;color:var(--muted)}
#view-address-quality .summary td,#view-address-quality .summary th{vertical-align:top}
#view-address-quality a{color:#0000a0}
'''

JS = r'''
(function(){
const tab=document.querySelector('[data-view="address-quality"]');
if(tab)tab.addEventListener('click',()=>{
  document.querySelectorAll('.tab').forEach(x=>x.classList.toggle('active',x===tab));
  document.querySelectorAll('.view').forEach(x=>x.classList.toggle('active',x.id==='view-address-quality'));
});
const openReview=document.querySelector('#aq-open-review');
if(openReview)openReview.addEventListener('click',()=>{
  const target=document.querySelector('[data-view="address-validation"]');
  if(target)target.click();
});
})();
'''


def patch_explorer(index_path: Path, payload: dict[str, Any]) -> None:
    html_text = index_path.read_text(encoding="utf-8")
    if 'data-view="address-quality"' in html_text:
        raise ValueError("Explorer already contains the address-quality tab")
    for marker in (TAB_MARKER, VIEW_MARKER, STYLE_MARKER, BODY_MARKER):
        if marker not in html_text:
            raise ValueError(f"Explorer template marker not found: {marker}")
    rendered = _render_quality_html(payload)
    html_text = html_text.replace(
        TAB_MARKER,
        '<button class="tab" data-view="address-quality">Qualità indirizzi</button>\n'
        + TAB_MARKER,
        1,
    )
    html_text = html_text.replace(
        VIEW_MARKER,
        f'<section class="view" id="view-address-quality">{rendered}</section>'
        + VIEW_MARKER,
        1,
    )
    html_text = html_text.replace(STYLE_MARKER, CSS + "\n" + STYLE_MARKER, 1)
    html_text = html_text.replace(BODY_MARKER, f"<script>{JS}</script>\n" + BODY_MARKER, 1)
    index_path.write_text(html_text, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Add source-backed address quality metrics to the private Dataset Explorer."
    )
    parser.add_argument("--index", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--address-results", type=Path, required=True)
    parser.add_argument("--frozen-review-summary", type=Path, required=True)
    parser.add_argument("--frozen-review-metadata", type=Path, required=True)
    parser.add_argument(
        "--address-results-href",
        default="address-validation/address_results.csv",
    )
    args = parser.parse_args()
    payload = build_quality_payload(
        summary_path=args.summary,
        address_results_path=args.address_results,
        frozen_review_summary_path=args.frozen_review_summary,
        frozen_review_metadata_path=args.frozen_review_metadata,
        address_results_href=args.address_results_href,
    )
    patch_explorer(args.index, payload)
    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
