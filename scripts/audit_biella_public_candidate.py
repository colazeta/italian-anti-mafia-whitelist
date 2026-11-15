"""Require an exact two-scope Biella delta; all other rows AND reports survive."""
from pathlib import Path
import json
import tempfile

from white_list_archive.publishing.biella_review import PROFILES, REFERENCE_DATE, SOURCE_SHA256
from white_list_archive.publishing.incremental_audit import audit_incremental
from white_list_archive.publishing.public_snapshot import restore


def main():
    manifest = json.loads(Path('data/publication/public_snapshot.json').read_text())
    if manifest['release_tag'] != 'public-data-43524455108-1':
        print(json.dumps({'biella_incremental_audit': 'not_applicable_to_later_baseline'}))
        return
    proposal = json.loads(Path('public-site/data/registry.json').read_text())
    with tempfile.TemporaryDirectory(prefix='biella-approved-baseline-') as td:
        restore(manifest, Path(td))
        approved = json.loads((Path(td)/'registry.json').read_text())
    changes = {key: {'count': profile['public_records'], 'statuses': profile['status_counts'],
                    'reference_date': REFERENCE_DATE, 'sha256': SOURCE_SHA256,
                    'parser': 'biella_html_' + ('listed' if key.endswith('-listed') else 'applicants')}
               for key, profile in PROFILES.items()}
    result = audit_incremental(proposal, approved, changes)
    before = {s['source_key']: s for s in approved['meta']['sources']}
    after = {s['source_key']: s for s in proposal['meta']['sources']}
    if any(after[k] != v for k, v in before.items() if k not in changes):
        raise ValueError('Unrelated source verification report changed')
    result['outside_scope_reports_changed'] = 0
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__': main()
