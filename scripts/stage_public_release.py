#!/usr/bin/env python3
"""Create a separate public-release draft. Does not use git, publish, or install."""
import argparse
import json
from pathlib import Path
import re
import shutil

ROOT = Path(__file__).resolve().parents[1]
PLUGIN_REL = Path('plugins/clinical-do-map')
# Deliberate allowlist: future local mapping runs must not enter a public export.
PLUGIN_FILES = [
    '.codex-plugin/plugin.json', '.claude-plugin/plugin.json',
    *['skills/do-map/' + p for p in [
        'SKILL.md', 'agents/openai.yaml', 'scripts/do_map.py', 'tests/test_workflow.py',
        'references/method.md', 'references/domains.md', 'references/cli.md',
        'references/recovery.md', 'assets/EXAMPLE.md', 'assets/demo_concepts.csv',
        'assets/demo_source.csv', 'assets/demo_priorities.md',
        'assets/procedure_priorities.md', 'assets/procedure_priority_rules.json',
    ]],
]


def stage(destination, author, repository, license_file=None, license_id=None):
    dest = Path(destination).expanduser().resolve()
    if dest.exists():
        raise ValueError('Destination must be a new directory')
    if dest == ROOT or (ROOT / 'plugins') in dest.parents or (ROOT / 'case-study') in dest.parents:
        raise ValueError('Choose a destination outside plugin source and the historical archive')
    if not author.strip() or any(ord(c) < 32 for c in author):
        raise ValueError('Provide a nonempty publisher name without control characters')
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*/[A-Za-z0-9][A-Za-z0-9_.-]*', repository):
        raise ValueError('--repository must be a GitHub OWNER/REPO identifier')
    if bool(license_file) != bool(license_id):
        raise ValueError('Supply both --license-file and --license-id, or neither for a draft')
    license_bytes = Path(license_file).expanduser().read_bytes() if license_file else None
    if license_bytes is not None and not license_bytes.strip():
        raise ValueError('License file is empty')
    paths = [(ROOT / PLUGIN_REL / name, PLUGIN_REL / name) for name in PLUGIN_FILES]
    paths += [(ROOT / 'scripts' / name, Path('scripts') / name)
              for name in ['install.py', 'package.py', 'stage_public_release.py']]
    paths += [(ROOT / name, Path(name)) for name in ['INSTALL.md', 'PUBLISH.md']]
    for source, _ in paths:
        if source.is_symlink() or not source.is_file():
            raise ValueError(f'Missing or symlinked release source: {source}')
    dest.mkdir(parents=True)
    for source, relative in paths:
        output = dest / relative
        output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, output)
    url = 'https://github.com/' + repository
    for host in ['.codex-plugin', '.claude-plugin']:
        manifest = dest / PLUGIN_REL / host / 'plugin.json'
        data = json.loads(manifest.read_text())
        data.update(author={'name': author}, repository=url, homepage=url)
        if license_id:
            data['license'] = license_id
        if host == '.codex-plugin':
            data['interface']['developerName'] = author
        manifest.write_text(json.dumps(data, indent=2) + '\n')
    codex = {'name': 'clinical-do-map', 'interface': {'displayName': 'CLINICAL DO MAP'},
             'plugins': [{'name': 'clinical-do-map',
                          'source': {'source': 'local', 'path': './plugins/clinical-do-map'},
                          'policy': {'installation': 'AVAILABLE', 'authentication': 'ON_INSTALL'},
                          'category': 'Productivity'}]}
    claude = {'name': 'clinical-do-map', 'owner': {'name': author},
              'plugins': [{'name': 'clinical-do-map', 'source': './plugins/clinical-do-map',
                           'description': 'Terminology review with local evidence and audited CSV updates.'}]}
    for relative, data in [('.agents/plugins/marketplace.json', codex), ('.claude-plugin/marketplace.json', claude)]:
        output = dest / relative
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(data, indent=2) + '\n')
    # In the public repository, the contents of mapping_with_agent are the root.
    for name in ['INSTALL.md', 'PUBLISH.md']:
        path = dest / name
        path.write_text(path.read_text().replace('mapping_with_agent/', './'))
    if license_bytes is not None:
        for relative in ['LICENSE', 'plugins/clinical-do-map/LICENSE',
                         'plugins/clinical-do-map/skills/do-map/LICENSE']:
            (dest / relative).write_bytes(license_bytes)
    else:
        (dest / 'LICENSE_REQUIRED.md').write_text(
            '# Draft: license decision needed\n\nAdd the publisher-approved code license before public release. '
            'This draft does not choose or grant a license. Terminology data have separate terms.\n')
    (dest / '.gitignore').write_text(
        '__pycache__/\n*.pyc\n.DS_Store\n.env\n.env.*\n/athena/\n/case-study/\n'
        '/validation/\n/reviews/\n/dist/\n*.sqlite\n*.sqlite-*\n')
    (dest / 'README.md').write_text(f'''# CLINICAL DO MAP

Reusable terminology mapping for agents that support Agent Skills and local Python tools.
Python 3.10+ with SQLite FTS5 is required. No third-party Python packages or model API keys are required by the scripts.

## Install

Codex CLI with plugin support:

```bash
codex plugin marketplace add {repository}
codex plugin add clinical-do-map@clinical-do-map
```

Claude Code:

```text
/plugin marketplace add {repository}
/plugin install clinical-do-map@clinical-do-map
```

Start a new session. Codex uses `$do-map`; the Claude plugin uses `/clinical-do-map:do-map`.
For plain `/do-map`, install the standalone Claude skill using [INSTALL.md](INSTALL.md).
Other Agent Skills hosts can use the standalone skill if they support local Python execution;
follow that host's skill discovery rules. Compatibility with every agent is not claimed.

## Use

```text
$do-map SNOMED Procedure research/priorities.md --input mapping.csv --athena athena --reviewer YourName --out reviews/procedure-01 --correct-targets --allow-wider
```

Omit `--apply` to produce a reviewed copy. Add it when updating the input is intended.
The agent evaluates meaning and writes explicit decisions. The scripts index vocabulary,
track coverage, check target eligibility, and apply a complete preview with backups and hash checks.
High scores and exact labels never automatically approve a mapping.

## Documentation

- [Detailed method](plugins/clinical-do-map/skills/do-map/references/method.md)
- [Domain profiles](plugins/clinical-do-map/skills/do-map/references/domains.md)
- [CLI and schemas](plugins/clinical-do-map/skills/do-map/references/cli.md)
- [Synthetic example](plugins/clinical-do-map/skills/do-map/assets/EXAMPLE.md)
- [Publishing and updates](PUBLISH.md)

## Check and build

```bash
python3 -m unittest discover -s plugins/clinical-do-map/skills/do-map/tests -v
python3 scripts/package.py
```

Tests verify workflow integrity, not clinical mapping accuracy. Use locally authorized terminology
exports and appropriate review for your intended use. No patient records, vocabulary distribution,
historical source catalogue or real mapping output is included in this repository.
''')
    return {'destination': str(dest), 'files': len([p for p in dest.rglob('*') if p.is_file()]),
            'repository': repository, 'license_supplied': license_bytes is not None,
            'published': False, 'globally_installed': False}


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--destination', required=True)
    p.add_argument('--author', required=True)
    p.add_argument('--repository', required=True)
    p.add_argument('--license-file')
    p.add_argument('--license-id')
    args = p.parse_args()
    try:
        print(json.dumps(stage(args.destination, args.author, args.repository,
                               args.license_file, args.license_id), indent=2))
    except (OSError, ValueError) as error:
        p.exit(2, f'ERROR: {error}\n')
