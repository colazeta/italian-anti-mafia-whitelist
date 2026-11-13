"""Reviewed Alessandria October delta against the selected Perugia baseline."""
from pathlib import Path
import json
import tempfile
from white_list_archive.publishing.incremental_audit import audit_incremental
from white_list_archive.publishing.public_snapshot import restore
from white_list_archive.parsers.alessandria_october import PROFILES


def main():
    manifest=json.loads(Path('data/publication/public_snapshot.json').read_text())
    if manifest['release_tag']!='public-data-43505431363-1':
        print(json.dumps({'alessandria_incremental_audit':'not_applicable_to_later_baseline'}));return
    proposed=json.loads(Path('public-site/data/registry.json').read_text())
    with tempfile.TemporaryDirectory(prefix='alessandria-approved-baseline-') as td:
        restore(manifest,Path(td));approved=json.loads((Path(td)/'registry.json').read_text())
    changes={'alessandria-'+label:{'count':p['records'],'statuses':p['statuses'],
             'reference_date':'2026-10-28','sha256':p['sha256'],'parser':'alessandria_'+label+'_2026_10'}
             for label,p in PROFILES.items()}
    print(json.dumps(audit_incremental(proposed,approved,changes),sort_keys=True))


if __name__=='__main__': main()
