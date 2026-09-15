# CLINICAL DO MAP

A clinical terminology mapping skill/plugin, a local review engine, and the preserved procedure-review case that led to it.

## Start here

1. [Install the skill or plugin](INSTALL.md).
2. Read [the detailed step-by-step method](plugins/clinical-do-map/skills/do-map/references/method.md).
3. Invoke the skill with your target, domain, priorities, source file and vocabulary.

To distribute this to others, follow [the publishing guide](PUBLISH.md). It includes a helper that exports a separate public repository with Codex and Claude marketplace catalogs. See [validation results](VALIDATION.md) for completed checks and their limits.

```text
/do-map SNOMED Procedure research/priorities.md --input future_mapping.csv --athena athena --reviewer Cuspal --out reviews/procedure-01 --correct-targets --allow-wider --apply
```

In Codex, use **`$do-map`** with the same arguments. A standalone Claude Code skill uses **`/do-map`**; plugin installations may use **`/clinical-do-map:do-map`**. This is an agent workflow command, not a shell command that automatically makes semantic decisions.

`--apply` authorizes updating the input after a complete validated preview. Omit it to receive an output copy. `--correct-targets` permits supported target corrections; `--allow-wider` permits acceptable broader mappings with documented information loss. Prior reviewed rows are protected unless re-review is requested.

## What is included

| Location | Contents |
|---|---|
| [plugins/clinical-do-map](plugins/clinical-do-map) | Portable Codex and Claude plugin manifests |
| [skills/do-map/SKILL.md](plugins/clinical-do-map/skills/do-map/SKILL.md) | Reusable agent command and workflow |
| [do_map.py](plugins/clinical-do-map/skills/do-map/scripts/do_map.py) | Vocabulary indexing/search, row queues, explicit decisions, coverage, rendering, protected apply and ancestry checks |
| [CLI reference](plugins/clinical-do-map/skills/do-map/references/cli.md) | Commands, CSV schemas, JSONL decisions and output contract |
| [Domain profiles](plugins/clinical-do-map/skills/do-map/references/domains.md) | Procedure, Drug, Condition, Measurement, Observation, Device, Unit, Visit and custom-domain review criteria |
| [Recovery guide](plugins/clinical-do-map/skills/do-map/references/recovery.md) | Resume, external edits, stale snapshots and interrupted updates |
| [CODE_INVENTORY.md](CODE_INVENTORY.md) | Original and new scripts, preparation outputs, evidence and reproduction paths |
| [scripts](scripts) | Installation, packaging, archival and historical lookup helpers |
| [tests](plugins/clinical-do-map/skills/do-map/tests) | Synthetic integration tests; no clinical gold-standard claims |
| [dist](dist) | Portable plugin/skill ZIPs and SHA256 checksums |

## What the agent and scripts each do

The **agent** interprets source meaning, reads research priorities, inspects vocabulary evidence, evaluates alternatives and writes an explicit decision for each row. The **scripts** preserve data, retrieve candidates, validate metadata/coverage and apply only a complete reviewed artifact. There is no score-threshold approval or exact-label auto-approval in this generalized version.

The engine accepts Athena-style or canonical comma/tab concept exports and customizable source columns. It does not directly parse every terminology distribution. Raw RF2, FHIR, UMLS, OWL or proprietary formats need a verified normalization step. One-to-many expansion, numeric/unit conversion, phenotype construction and live ETL deployment remain separate tasks.

## Original procedure review result

The preserved run reviewed **6,963 rows**: **4,140 APPROVED**, **2,823 FLAGGED**, with **539 target corrections**. Of the approvals, **1,533 were WIDER**, with information loss documented. This was AI-assisted review under the requested `Cuspal` attribution, not independent human clinical certification. The original file and its review outputs were not changed while building this package.

## Run the checks

From the project root:

```bash
python3 -m unittest discover -s mapping_with_agent/plugins/clinical-do-map/skills/do-map/tests -v
python3 mapping_with_agent/scripts/verify_archive.py mapping_with_agent/case-study/procedure-2026-09-16
```

The portable ZIPs exclude the historical archive. That archive contains local catalogue and SNOMED-derived data; apply the relevant data/terminology licenses before sharing it. The original Athena distribution is not bundled. No global installation is performed by creating this folder.

## License

The original software and documentation are licensed under the [MIT License](LICENSE), copyright (c) 2026 Clinical Do Map contributors.

Third-party terminology, source catalogues, and derived clinical data, including the real-case validation artifacts, remain subject to their respective licenses and permissions. The MIT License does not grant rights to those materials.
