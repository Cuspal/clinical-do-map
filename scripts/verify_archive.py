#!/usr/bin/env python3
"""Verify the byte-exact historical snapshot without running its mutation scripts."""
import argparse
import hashlib
import json
from pathlib import Path


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('archive', type=Path)
    args = p.parse_args()
    inventory = json.loads((args.archive / 'archive_inventory.json').read_text())
    for record in inventory:
        path = (args.archive / record['path']).resolve()
        if not path.is_relative_to(args.archive.resolve()):
            p.exit(2, 'Inventory path escapes archive\n')
        if hashlib.sha256(path.read_bytes()).hexdigest() != record['sha256']:
            p.exit(2, f'Hash mismatch: {record["path"]}\n')
    print(f'PASS: {len(inventory)} archived files match their captured hashes')


if __name__ == '__main__':
    main()
