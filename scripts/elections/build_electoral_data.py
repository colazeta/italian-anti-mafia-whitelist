"""Build a descriptive electoral update-time dataset from preserved onData extracts.

Usage: python scripts/elections/build_electoral_data.py --european FILE
  --camera FILE --senate FILE --referendum-results FILE
  --referendum-registry FILE --output public-site/data/electoral.json

The source's dt_agg is an update timestamp, not a verified first-completion
or a prefectural processing timestamp. Ballots from one election are combined
per municipality, counting the number of sections only once.
"""
import argparse
from collections import defaultdict
import csv
from datetime import datetime
from hashlib import sha256
from io import StringIO
import json
from pathlib import Path
import re
import unicodedata


def read(path):
    content = Path(path).read_bytes()
    return list(csv.DictReader(StringIO(content.decode('utf-8-sig'), newline=''))), sha256(content).hexdigest()


def _rollup(rows, key):
    groups = defaultdict(list)
    for row in rows:
        groups[key(row)].append(row)
    rolled = {}
    for municipality, group in groups.items():
        totals = [int(r['sz_tot']) for r in group]
        arrived = [int(r['sz_perv']) for r in group]
        timestamps = [r['dt_agg'] for r in group]
        rolled[municipality] = dict(province_code=group[0]['cod_prov'],
                                    province=group[0]['desc_prov'],
                                    sections=sum(totals), reported=sum(arrived),
                                    timestamp=max(timestamps) if all(timestamps) else '',
                                    valid=all(0 <= n <= t for n, t in zip(arrived, totals)))
    return rolled


def combine_ballots(ballots, key):
    """Use the last ballot update per municipality; never multiply its sections."""
    rolled = [_rollup(rows, key) for rows in ballots]
    combined = []
    for municipality in sorted(set().union(*(set(group) for group in rolled))):
        pieces = [group.get(municipality) for group in rolled]
        present = [piece for piece in pieces if piece is not None]
        totals = {piece['sections'] for piece in present}
        valid = len(present) == len(ballots) and len(totals) == 1 and all(
            piece['valid'] and piece['reported'] == piece['sections'] and piece['timestamp']
            for piece in present)
        exemplar = present[0]
        expected = exemplar['sections']
        combined.append(dict(cod_prov=exemplar['province_code'], desc_prov=exemplar['province'],
                             municipality_key=str(municipality), sz_tot=str(expected),
                             sz_perv=str(expected) if valid else '',
                             dt_agg=max(piece['timestamp'] for piece in present) if valid else ''))
    return combined


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
                    municipalities=len({r.get('municipality_key') or r.get('CODICE ISTAT') or r.get('comune') or r.get('codice') for r in group}),
                    sections_expected=sum(int(r['sz_tot']) for r in group),
                    sections_reported=sum(int(r['sz_perv']) for r in group)
                    if all(str(r['sz_perv']).isdigit() for r in group) else None,
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


METRICS = ('weighted_mean_hours', 'weighted_p90_hours', 'last_hours')


def province_key(name):
    return re.sub('[^A-Z]', '', unicodedata.normalize('NFKD', name.upper()))


def overall_ranking(events):
    names = {}
    by_event = {}
    percentiles = {}
    for election in events:
        rows = {province_key(r['province']): r for r in election['provinces']}
        if len(rows) != len(election['provinces']):
            raise ValueError('ambiguous province name in election')
        by_event[election['id']] = rows
        names.update({key: row['province'] for key, row in rows.items()})
        for metric in METRICS:
            complete = {key: row[metric] for key, row in rows.items() if row['status'] == 'complete_in_extract'}
            ordered = sorted(complete.values())
            if len(ordered) < 2:
                raise ValueError('insufficient complete provinces for percentile ranking')
            # Midrank gives identical timestamps identical positions.
            percentiles[election['id'], metric] = {
                key: round(100 * (ordered.index(value) + (len(ordered) - 1 - ordered[::-1].index(value))) / 2 / (len(ordered) - 1), 6)
                for key, value in complete.items()
            }
    rows = []
    for key in sorted(names):
        available = [e['id'] for e in events if key in by_event[e['id']]
                     and by_event[e['id']][key]['status'] == 'complete_in_extract']
        item = dict(province=names[key], events_complete=len(available),
                    status='complete_in_all' if len(available) == len(events) else 'incomplete_coverage')
        if len(available) == len(events):
            item['scores'] = {metric: round(sum(percentiles[e['id'], metric][key] for e in events) / len(events), 3)
                              for metric in METRICS}
            item['event_hours'] = {e['id']: {metric: by_event[e['id']][key][metric] for metric in METRICS}
                                   for e in events}
        rows.append(item)
    return dict(method='Equal-weight mean of within-election provincial percentile midranks (0 fastest, 100 slowest); only provinces complete in all four elections are ranked.',
                elections_required=len(events), provinces=rows)


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
    if set(by_question) != {str(n) for n in range(1, 6)}:
        raise ValueError('expected five referendum questions')
    politics = combine_ballots([camera, senate], lambda r: (r['cod_prov'], r['cod_com']))
    referendum = combine_ballots([by_question[str(n)] for n in range(1, 6)], lambda r: r['comune'])
    events = [event('eu-2024', 'Europee 2024', 'european', euro, datetime(2024, 6, 9, 23),
                    'https://github.com/ondata/elezioni_europee_2024', {'municipal': eh},
                    'Voti italiani; l’estratto conserva alcune province incomplete.'),
              event('politiche-2022', 'Politiche 2022', 'political', politics,
                    datetime(2022, 9, 25, 23), 'https://github.com/ondata/elezioni-politiche-2022',
                    {'camera': ch, 'senato': sh},
                    'Ultimo aggiornamento comunale tra Camera e Senato; sezioni contate una volta. Comuni senza entrambi i rami restano fuori classifica.'),
              event('referendum-2022', 'Referendum abrogativi 2022', 'referendum', referendum,
                    datetime(2022, 6, 12, 23), 'https://github.com/ondata/elezioni_2022',
                    {'results': qh, 'registry': rh},
                    'Ultimo aggiornamento comunale tra i cinque quesiti; sezioni contate una volta.')]
    r20 = [dict(cod_prov=r['CODICE ISTAT'][:3], desc_prov=r['desc_prov'],
                sz_perv=r['sezioni_pervenute'], sz_tot=r['sezioni_totali'],
                dt_agg=r['dataAggiornamentoDati'], **{'CODICE ISTAT':r['CODICE ISTAT']})
           for r in constitutional]
    events.append(event('referendum-2020', 'Referendum costituzionale 2020 · parlamentari',
                        'referendum', r20, datetime(2020, 9, 21, 15),
                        'https://github.com/ondata/elezioni_2020', {'municipal': r20h},
                        'Il voto si è chiuso lunedì alle 15:00; prima dello scrutinio referendario si svolgevano le suppletive dove previste.'))
    payload={'schema_version':2,'method':'latest ballot update per municipality and election; sections counted once and inherit the row timestamp; no prefectural attribution',
             'events':events, 'overall':overall_ranking(events)}
    Path(a.output).parent.mkdir(parents=True, exist_ok=True)
    Path(a.output).write_text(json.dumps(payload,ensure_ascii=False,separators=(',',':'))+'\n',encoding='utf-8')
    print([(e['id'],len(e['provinces']),sum(p['status']=='complete_in_extract' for p in e['provinces'])) for e in events])

if __name__ == '__main__':
    main()
