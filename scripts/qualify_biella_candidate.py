"""Exact original/source QA, with no approval, persistence or publication."""
from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile

from white_list_archive.publishing.biella_review import qualify
from white_list_archive.publishing.public_national_registry import _download


def main():
    manifest = json.loads(Path('data/publication/public_snapshot.json').read_text())
    if manifest['release_tag'] != 'public-data-43524455108-1':
        print(json.dumps({'biella_source_qa': 'not_applicable_to_later_baseline'}))
        return
    config = json.loads(Path('data/publication/multi_prefecture_pilot.json').read_text())
    selected = [s for s in config['sources'] if s['authority_key'] == 'biella']
    if {s['source_key'] for s in selected} != {'biella-listed', 'biella-applicants'}:
        raise ValueError('Incomplete Biella source selection')
    results = []
    with tempfile.TemporaryDirectory(prefix='biella-exact-source-') as td:
        path = Path(td)/'source.html'
        _download(selected[0]['resource_url'], path)
        for cfg in selected:
            batch = qualify(path, cfg, checked_at=datetime.now(timezone.utc).isoformat())
            results.append({'source_key': cfg['source_key'], 'reference_date': cfg['reference_date'],
                            'sha256': cfg['sha256'], 'parser_diagnostics': batch.diagnostics})
    print(json.dumps({'source_qa': results, 'publication_performed': False}, sort_keys=True))


if __name__ == '__main__': main()
