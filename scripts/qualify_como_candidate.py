"""Run the package-owned exact Como review without approving or publishing."""
import argparse
import json
from pathlib import Path

from white_list_archive.publishing import como_review
from white_list_archive.publishing.publication_handoff import _digest


def selected_como_mode(config, preserved, selected_manifest, intent):
    """Return 'preserved' only for complete previously selected Como scopes.

    This is invoked after the full public registry builder has already
    restored and verified every approved derivative and source descriptor.
    Incomplete preservation or a *current* intent targeting Como fails closed.
    """
    keys = set(como_review.PINS)
    all_keys = {source['source_key'] for source in config['sources']}
    if not isinstance(preserved, list) or not all(isinstance(x, str) for x in preserved):
        raise ValueError('Invalid explicit preserved-source list')
    if len(preserved) != len(set(preserved)) or set(preserved) - all_keys:
        raise ValueError('Duplicate or unknown preserved source')
    if keys - all_keys:
        raise ValueError('Missing configured Como population')
    both = keys & set(preserved)
    if both == keys:
        if (intent.get('baseline_manifest_sha256') == _digest(selected_manifest)
                and keys.intersection(intent.get('changes', {}))):
            raise ValueError('Current Como release intent cannot be silently preserved')
        return 'preserved'
    if both:
        raise ValueError('Partially preserved Como pair requires explicit review')
    return 'fresh'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reviewed-config', action='store_true')
    parser.add_argument('--respect-selected-preservation', action='store_true',
                        help='Main-only: skip live review solely for an already approved immutable Como pair')
    args = parser.parse_args(argv)
    if args.respect_selected_preservation:
        config = json.loads(Path('data/publication/multi_prefecture_pilot.json').read_text())
        preserved = json.loads(Path('data/publication/preserved_public_sources.json').read_text())
        selected = json.loads(Path('data/publication/public_snapshot.json').read_text())
        intent = json.loads(Path('data/publication/incremental_release_intent.json').read_text())
        mode = selected_como_mode(config, preserved, selected, intent)
        if mode == 'preserved':
            print(json.dumps({'scope': 'como', 'state': 'selected_immutable_pair_reused',
                              'publications': 0, 'approval_granted': False}, sort_keys=True))
            return 0
    return como_review.main(reviewed_config=args.reviewed_config)


if __name__ == '__main__':
    raise SystemExit(main())
