#!/usr/bin/env python3
"""Exercise install/export/build helpers in disposable directories only."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def check(condition, message):
    if not condition:
        raise RuntimeError(message)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out', type=Path)
    args = p.parse_args()
    installer, exporter = load('install'), load('stage_public_release')
    checks = []
    with tempfile.TemporaryDirectory(prefix='do-map-package-') as raw:
        work = Path(raw)
        for host in ['codex', 'claude', 'codex-plugin', 'claude-plugin']:
            dest = work / host
            installer.install(host, dest, True)
            check(not dest.exists(), f'{host} dry-run wrote files')
            installer.install(host, dest)
            skill = (dest if host in {'codex', 'claude'} else
                     dest / ('plugins/clinical-do-map/skills/do-map' if host == 'codex-plugin' else 'skills/do-map'))
            result = subprocess.run([sys.executable, str(skill / 'scripts/do_map.py'), 'doctor'],
                                    check=True, capture_output=True, text=True)
            check(bool(result.stdout), 'doctor returned no result')
            try:
                installer.install(host, dest)
            except ValueError:
                pass
            else:
                raise RuntimeError('Installer overwrote existing destination')
            checks.append(host + ': dry-run, copy, doctor, overwrite refusal')
        dest = work / 'public'
        license_file = work / 'fixture-license.txt'
        license_file.write_text('Synthetic license fixture for disposable validation only.\n')
        exporter.stage(dest, 'Synthetic Test Publisher', 'example/clinical-do-map', license_file, 'LicenseRef-Test')
        check(not any(p.name in {'case-study', 'validation', 'athena', '__pycache__'}
                      or p.suffix in {'.sqlite', '.pyc'} for p in dest.rglob('*')), 'Private/runtime file in export')
        check(not any(str(ROOT).encode() in p.read_bytes() for p in dest.rglob('*') if p.is_file()),
              'Local absolute path leaked into export')
        for catalog in ['.agents/plugins/marketplace.json', '.claude-plugin/marketplace.json']:
            data = json.loads((dest / catalog).read_text())
            check(data['name'] == 'clinical-do-map', 'Wrong marketplace name')
            check(data['plugins'][0]['name'] == 'clinical-do-map', 'Wrong plugin name')
        if shutil.which('claude'):
            for path in [dest, dest / 'plugins/clinical-do-map']:
                subprocess.run(['claude', 'plugin', 'validate', str(path), '--json'],
                               check=True, capture_output=True, text=True)
            checks.append('Claude validates exported catalog and plugin')
        subprocess.run([sys.executable, str(dest / 'scripts/package.py')], check=True, capture_output=True)
        for line in (dest / 'dist/SHA256SUMS').read_text().splitlines():
            digest, filename = line.split('  ')
            archive_path = dest / 'dist' / filename
            check(hashlib.sha256(archive_path.read_bytes()).hexdigest() == digest, 'ZIP checksum mismatch')
            with zipfile.ZipFile(archive_path) as archive:
                check(archive.testzip() is None, 'Corrupt ZIP')
                check('LICENSE' in archive.namelist(), 'License missing in ZIP')
                check(not any('case-study' in name or name.endswith(('.sqlite', '.pyc'))
                              for name in archive.namelist()), 'Private/runtime file in ZIP')
        checks.append('Public export: both catalogs, publisher metadata, separate license, no private files/local paths')
        checks.append('Both ZIPs: integrity, license inclusion and SHA256 verification')
        exporter.stage(work / 'draft', 'Synthetic Test Publisher', 'example/clinical-do-map')
        check((work / 'draft/LICENSE_REQUIRED.md').exists(), 'Unlicensed draft is not labeled')
        checks.append('Unlicensed export is explicitly labeled a draft')
    result = {'status': 'PASS', 'checks': checks, 'global_installation': False, 'network_publication': False}
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
