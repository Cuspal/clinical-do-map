# Installation manual

## Requirements

- Python 3.10 or newer, including SQLite FTS5.
- A host that supports Agent Skills: Codex or Claude Code for the examples below.
- For real mappings, a locally available terminology export and permission to use it.

The scripts use the standard library. They need no model API key, package installation or database server. The agent host supplies the semantic review. Your shell may use `python` or `py -3` instead of `python3` on Windows.

Run all commands below from the repository containing `mapping_with_agent/`, or use absolute paths. To publish for other users, see [PUBLISH.md](PUBLISH.md).

## Option A — standalone Codex skill

Preview the destination:

```bash
python3 mapping_with_agent/scripts/install.py --host codex --dry-run
```

Install:

```bash
python3 mapping_with_agent/scripts/install.py --host codex
```

The default is `$CODEX_HOME/skills/do-map`, or `~/.codex/skills/do-map` when `CODEX_HOME` is not set. To use a host configured for `~/.agents/skills`, or any other discovered skill directory, specify the exact final skill folder:

```bash
python3 mapping_with_agent/scripts/install.py --host codex --destination ~/.agents/skills/do-map
```

Start a new conversation and invoke:

```text
$do-map SNOMED Procedure research/priorities.md --input mapping.csv --athena athena --reviewer Cuspal --out reviews/procedure-01 --correct-targets --allow-wider --apply
```

Codex skill invocation is `$do-map`; this package does not claim that the Codex slash menu exposes arbitrary custom `/do-map` commands. You can also explicitly ask Codex to use the supplied `SKILL.md` by its absolute path.

## Option B — standalone Claude Code skill with /do-map

```bash
python3 mapping_with_agent/scripts/install.py --host claude
```

This copies the self-contained skill to `~/.claude/skills/do-map`. Start a new session and use `/do-map` with the arguments shown in the README. To install at project scope:

```bash
python3 mapping_with_agent/scripts/install.py --host claude --destination /path/to/project/.claude/skills/do-map
```

Claude Code discovers standalone skills under its skills folders and exposes `/skill-name`; plugin skills are namespaced. [Official Claude Code skill documentation](https://code.claude.com/docs/en/skills).

## Option C — Codex plugin through an explicit local marketplace

Prepare a marketplace copy at a **new directory** of your choice:

```bash
python3 mapping_with_agent/scripts/install.py --host codex-plugin --destination ~/clinical-do-map-marketplace
```

The helper copies only the portable plugin and creates `.agents/plugins/marketplace.json` within that destination. It does not register the marketplace or modify global Codex configuration. Then run:

```bash
codex plugin marketplace add ~/clinical-do-map-marketplace
codex plugin add clinical-do-map@clinical-do-map
```

These subcommands were checked against the locally installed Codex CLI when the package was built. Check `codex plugin --help` if your host version differs. If `clinical-do-map` is already registered, use the existing marketplace or choose a deliberately renamed copy instead of creating a conflicting registration. Start a new conversation after installation. Invoke the discovered `do-map` skill with `$do-map` or select the plugin's skill in the host UI.

The optional marketplace is created only when you run this installation mode. The package build itself does not register or install a marketplace.

## Option D — Claude Code plugin for a session

The source folder already has `.claude-plugin/plugin.json`. Use a local plugin directory:

```bash
claude --plugin-dir /absolute/path/to/mapping_with_agent/plugins/clinical-do-map
```

Or copy it first:

```bash
python3 mapping_with_agent/scripts/install.py --host claude-plugin --destination ~/clinical-do-map-plugin
claude --plugin-dir ~/clinical-do-map-plugin
```

The plugin skill invocation is `/clinical-do-map:do-map`. The plain `/do-map` name is available through the standalone installation above. Check your host's plugin-directory support if running a different version; the command does not install a global marketplace.

## ZIP installation

`dist/do-map-1.0.0.zip` contains the skill contents; extract them into a `do-map` folder within a discovered skills directory. `dist/clinical-do-map-1.0.0.zip` contains the plugin root contents, including both host manifests. Check `dist/SHA256SUMS` before transferring. Use a host's import UI only if it supports the corresponding archive format; the copy/CLI methods above are the documented fallback.

## Verify installation

```bash
python3 ~/.codex/skills/do-map/scripts/do_map.py doctor
python3 -m unittest discover -s ~/.codex/skills/do-map/tests -v
```

Substitute the actual installation directory for another host/location. `doctor` reports Python, SQLite and FTS5. A new session should discover `do-map`. If it does not, check the selected host's skill directory and restart the session; copying files cannot refresh an already-loaded skill catalog.

To test the workflow without real terminology data, use the bundled synthetic assets and the instructions in [the example guide](plugins/clinical-do-map/skills/do-map/assets/EXAMPLE.md).

## Upgrade or uninstall

The installer refuses to overwrite an existing destination. Keep a backup or move the previous installation, then install the new version. Do not overwrite local customizations accidentally. A standalone uninstall removes only the installed `do-map` folder you chose; it does not require deleting mapping runs or backups. For a marketplace plugin, use the host's plugin removal/update commands and start a new conversation.

Do not put patient data, actual vocabulary downloads or the historical case archive inside the installed plugin. Runtime mapping outputs belong in the working project, so updating a skill cannot erase review progress.
