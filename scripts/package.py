#!/usr/bin/env python3
"""Build portable skill/plugin archives; exclude the historical clinical data."""
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    plugin = ROOT / 'plugins' / 'clinical-do-map'
    version = json.loads((plugin / '.codex-plugin/plugin.json').read_text())['version']
    dist = ROOT / 'dist'
    dist.mkdir(exist_ok=True)
    sums = []
    for name, source in [('clinical-do-map', plugin), ('do-map', plugin / 'skills/do-map')]:
        dest = dist / f'{name}-{version}.zip'
        with zipfile.ZipFile(dest, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(source.rglob('*')):
                if path.is_file() and '__pycache__' not in path.parts and path.suffix != '.pyc':
                    archive.write(path, path.relative_to(source))
        sums.append(hashlib.sha256(dest.read_bytes()).hexdigest() + '  ' + dest.name)
    (dist / 'SHA256SUMS').write_text('\n'.join(sums) + '\n')
    print('\n'.join(sums))


if __name__ == '__main__':
    main()
