"""Build a descriptive electoral update-time dataset from preserved onData extracts.

Usage: python scripts/elections/build_electoral_data.py --european FILE
  --camera FILE --senate FILE --referendum-results FILE
  --referendum-registry FILE --output public-site/data/electoral.json

The source's dt_agg is an update timestamp, not a verified first-completion
or a prefectural processing timestamp. No cross-event resource score is made.
"""
import argparse
from collections import defaultdict
import csv
from datetime import datetime
from hashlib import sha256
from io import StringIO
import json
from pathlib import Path


def read(path):
    content = Path(path).read_bytes()
    return list(csv.DictReader(StringIO(content.decode('utf-8-sig'), newline=''))), sha256(content).hexdigest()


def compute(rows, start):
    groups = defaultdict(list)
    for r in rows:
        groups[(str(r['cod_prov']), r['desc_prov'])].append(r)
    result = []
    for (code, name), group in sorted(groups.items(), key=lambda pair: int(pair[0][0])):
        valid = all(str(r['sz_perv']).isdigit() and str(r['sz_tot']).isdigit()
                    and int(r['sz_tot']) > 0 and int(r['sz_perv']) <= int(r['sz_tot'])
                    and str(r['dt_agg']).isdigit() and len(str(r['dt_agg'])) == 14 for r in group)
        complete = valid and all(r['sz_perv'] == r['sz_tot'] for r in group)
        item = dict(province_code=code, province=name, rows=len(group),
                    municipalities=len({r.get('CODICE ISTAT') or r.get('comune') or r.get('codice') for r in group}),
                    sections_expected=sum(int(r['sz_tot']) for r in group),
                    sections_reported=sum(int(r['sz_perv']) for r in group),
                    status='complete_in_extract' if complete else 'incomplete_or_invalid')
        if complete:
            points = sorted(((datetime.strptime(r['dt_agg'], '%Y%m%d%H%M%S') - start).total_seconds() / 3600,
                             int(r['sz_tot'])) for r in group)
            total = sum(n for _, n in points)
            cumulative = 0
            for hour, count in points:
                cumulative += count
                if cumulative >= .9 * total:
                    p90 = hour
                    break
            item.update(last_update_local=max(datetime.strptime(r['dt_agg'], '%Y%m%d%H%M%S') for r in group).isoformat(),
                        last_hours=round(points[-1][0], 3),
                        weighted_mean_hours=round(sum(t * n for t, n in points) / total, 3),
                        weighted_p90_hours=round(p90, 3))
        result.append(item)
    return result


def event(event_id, label, kind, rows, start, source_url, hashes, note):
    return dict(id=event_id, label=label, kind=kind, poll_close_local=start.isoformat(),
                provenance=dict(repository=source_url, sha256=hashes), note=note,
                provinces=compute(rows, start))


def main():
    parser = argparse.ArgumentParser()
    for name in ('european', 'camera', 'senate', 'referendum-results', 'referendum-registry', 'referendum-2020', 'output'):
        parser.add_argument('--' + name, required=True)
    a = parser.parse_args()
    euro, eh = read(a.european)
    camera, ch = read(a.camera)
    senate, sh = read(a.senate)
    questions, qh = read(a.referendum_results)
    registry, rh = read(a.referendum_registry)
    constitutional, r20h = read(a.referendum_2020)
    lookup = {r['comune']: r for r in registry}
    if len(lookup) != len(registry):
        raise ValueError('duplicate referendum municipality registry key')
    by_question = defaultdict(list)
    for r in questions:
        if r['comune'] not in lookup:
            raise ValueError('unmatched referendum municipality')
        by_question[r['cod']].append({**lookup[r['comune']], **r})
    events = [event('eu-2024', 'Europee 2024', 'european', euro, datetime(2024, 6, 9, 23),
                    'https://github.com/ondata/elezioni_europee_2024', {'municipal': eh},
                    'Voti italiani; l’estratto conserva alcune province incomplete.'),
              event('camera-2022', 'Politiche 2022 · Camera', 'political', camera,
                    datetime(2022, 9, 25, 23), 'https://github.com/ondata/elezioni-politiche-2022',
                    {'municipal': ch}, 'Alcuni comuni sono ripartiti su più righe di collegio; Valle d’Aosta è archiviata separatamente.'),
              event('senato-2022', 'Politiche 2022 · Senato', 'political', senate,
                    datetime(2022, 9, 25, 23), 'https://github.com/ondata/elezioni-politiche-2022',
                    {'municipal': sh}, 'Lo scrutinio del Senato precedeva quello della Camera; alcune aree hanno un regime o archivio distinto.')]
    labels={'1':'Incandidabilità', '2':'Misure cautelari', '3':'Separazione delle funzioni',
            '4':'Valutazione dei magistrati', '5':'Candidature al CSM'}
    for code in sorted(by_question):
        events.append(event('referendum-2022-' + code, 'Referendum 2022 · ' + code + '. ' + labels[code],
                            'referendum', by_question[code], datetime(2022, 6, 12, 23),
                            'https://github.com/ondata/elezioni_2022',
                            {'results': qh, 'registry': rh},
                            'Quesito ' + code + ' di 5; lo stesso comune può avere orari di aggiornamento diversi per quesito.'))
    r20 = [dict(cod_prov=r['CODICE ISTAT'][:3], desc_prov=r['desc_prov'],
                sz_perv=r['sezioni_pervenute'], sz_tot=r['sezioni_totali'],
                dt_agg=r['dataAggiornamentoDati'], **{'CODICE ISTAT':r['CODICE ISTAT']})
           for r in constitutional]
    events.append(event('referendum-2020', 'Referendum costituzionale 2020 · parlamentari',
                        'referendum', r20, datetime(2020, 9, 21, 15),
                        'https://github.com/ondata/elezioni_2020', {'municipal': r20h},
                        'Il voto si è chiuso lunedì alle 15:00; prima dello scrutinio referendario si svolgevano le suppletive dove previste.'))
    payload={'schema_version':1,'method':'latest municipal row dt_agg; sections inherit the row timestamp; no prefectural attribution',
             'events':events}
    Path(a.output).parent.mkdir(parents=True, exist_ok=True)
    Path(a.output).write_text(json.dumps(payload,ensure_ascii=False,separators=(',',':'))+'\n',encoding='utf-8')
    print([(e['id'],len(e['provinces']),sum(p['status']=='complete_in_extract' for p in e['provinces'])) for e in events])

if __name__ == '__main__':
    main()
