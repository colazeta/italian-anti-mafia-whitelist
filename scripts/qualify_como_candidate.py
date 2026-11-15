"""Run the package-owned exact Como review without approving or publishing."""
import argparse
from white_list_archive.publishing.como_review import main

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reviewed-config', action='store_true')
    raise SystemExit(main(reviewed_config=parser.parse_args().reviewed_config))
