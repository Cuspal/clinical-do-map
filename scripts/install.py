#!/usr/bin/env python3
"""Copy a standalone skill or prepare a local plugin marketplace. Never overwrite."""
import argparse
import json
import os
from pathlib import Path
import shlex
import shutil

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / 'plugins' / 'clinical-do-map'
SKILL = PLUGIN / 'skills' / 'do-map'


def install(host, destination=None, dry_run=False):
    if destination:
        dest = Path(destination).expanduser().absolute()
    elif host == 'codex':
        dest = Path(os.environ.get('CODEX_HOME', Path.home() / '.codex')).expanduser() / 'skills' / 'do-map'
    elif host == 'claude':
        dest = Path.home() / '.claude' / 'skills' / 'do-map'
    else:
        raise ValueError('--destination is required for a local plugin marketplace or plugin copy')
    if dest.exists() or dest.is_symlink():
        raise ValueError(f'Destination already exists; preserve or move it before installing: {dest}')
    dest = dest.resolve()
    if dest == ROOT or (ROOT / 'plugins') in dest.parents or (ROOT / 'case-study') in dest.parents:
        raise ValueError('Do not install over package source or case-study directories')
    result = {'host': host, 'destination': str(dest), 'dry_run': dry_run}
    if host == 'codex-plugin':
        marketplace_name = 'clinical-do-map'
        result['next_commands'] = [
            'codex plugin marketplace add ' + shlex.quote(str(dest)),
            'codex plugin add clinical-do-map@' + marketplace_name,
        ]
        if not dry_run:
            shutil.copytree(PLUGIN, dest / 'plugins' / 'clinical-do-map', ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
            market = dest / '.agents' / 'plugins' / 'marketplace.json'
            market.parent.mkdir(parents=True)
            market.write_text(json.dumps({'name': marketplace_name, 'interface': {'displayName': 'CLINICAL DO MAP'},
                'plugins': [{'name': 'clinical-do-map', 'source': {'source': 'local', 'path': './plugins/clinical-do-map'},
                             'policy': {'installation': 'AVAILABLE', 'authentication': 'ON_INSTALL'}, 'category': 'Productivity'}]}, indent=2) + '\n')
    elif host == 'claude-plugin':
        result['next_commands'] = ['claude --plugin-dir ' + shlex.quote(str(dest))]
        if not dry_run:
            shutil.copytree(PLUGIN, dest, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    else:
        result['invocation'] = '$do-map' if host == 'codex' else '/do-map'
        if not dry_run:
            shutil.copytree(SKILL, dest, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    result['note'] = 'Start a new conversation after installation. No agent configuration or marketplace registration was changed by this copy helper.'
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', choices=['codex', 'claude', 'codex-plugin', 'claude-plugin'], required=True)
    parser.add_argument('--destination')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    try:
        print(json.dumps(install(args.host, args.destination, args.dry_run), indent=2))
    except (OSError, ValueError) as e:
        parser.exit(2, f'ERROR: {e}\n')
