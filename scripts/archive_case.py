#!/usr/bin/env python3
"""Archive the original review code and authored/generated preparation evidence.

Copies local clinical vocabulary derivatives outside the distributable plugin.
Does not copy the original Athena distribution or alter the reviewed source.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', type=Path, default=ROOT.parent)
    parser.add_argument('--destination', type=Path, default=ROOT / 'case-study' / 'procedure-2026-09-16')
    args = parser.parse_args()
    source = args.project.resolve() / 'mapping_usagi_final'
    dest = args.destination.resolve()
    if dest.exists():
        parser.exit(2, 'Archive destination exists; refusing to overwrite the historical record\n')
    output = dest / 'mapping_usagi_final'
    output.mkdir(parents=True)
    inventory = []
    paths = [source / 'review_procedures.py', source / 'apply_procedure_review.py', source / 'mapping_procedure_final.csv']
    paths += [p for p in (source / 'procedure_review').iterdir() if p.is_file()]
    for p in sorted(paths):
        relative = p.relative_to(source)
        target = output / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, target)
        digest = hashlib.sha256(target.read_bytes()).hexdigest()
        if digest != hashlib.sha256(p.read_bytes()).hexdigest():
            raise RuntimeError('Archive verification failed: ' + str(p))
        inventory.append({'path': str(target.relative_to(dest)), 'source_path_at_capture': str(p),
                          'sha256': digest, 'bytes': target.stat().st_size})
    (dest / 'archive_inventory.json').write_text(json.dumps(inventory, indent=2) + '\n')
    print(json.dumps({'files': len(inventory), 'bytes': sum(x['bytes'] for x in inventory), 'destination': str(dest)}, indent=2))


if __name__ == '__main__':
    main()
