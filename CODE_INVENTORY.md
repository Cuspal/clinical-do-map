# Code and preparation inventory

## Reusable code

| File | Responsibility |
|---|---|
| `plugins/clinical-do-map/skills/do-map/scripts/do_map.py` | Full domain-neutral mechanics; no automatic semantic approval or model API |
| `plugins/clinical-do-map/skills/do-map/tests/test_workflow.py` | Synthetic end-to-end and failure-path tests |
| `scripts/install.py` | Standalone Codex/Claude skill copies and optional local marketplace/plugin preparation |
| `scripts/package.py` | Builds plugin/skill ZIPs excluding historical clinical data |
| `scripts/stage_public_release.py` | Exports an explicit portable file list, public README and both host marketplace catalogs into a new folder; does not publish |
| `scripts/validate_package.py` | Tests all install modes, public export boundaries, manifests, license inclusion and ZIP checksums in disposable folders |
| `scripts/archive_case.py` | Copies retained original artifacts and records byte-level hashes; refuses overwrite |
| `scripts/verify_archive.py` | Verifies every archived file against inventory |
| `scripts/case_helpers.py` | Read-only historical group inspection, FTS search and decision-coverage checks |
| `scripts/validate_real_case.py` | Replays all archived judgments through the generic engine in a new isolated workspace; does not apply changes |

The skill's references hold the detailed method, per-domain review rules, schemas, CLI commands and recovery procedures. Assets contain only explicitly synthetic sample data plus a reusable priority template; the historical record is outside the portable plugin.

## Original code, preserved

Within `case-study/procedure-2026-09-16/mapping_usagi_final/`:

- `review_procedures.py`: original preparation script, source grouping, priority tags, vocabulary metadata extraction, synonym matching and FTS index construction.
- `apply_procedure_review.py`: original decision parser, target validation, review field changes, audit/queue exports, previews and atomic source replacement.
- `procedure_review/decisions_*.tsv`: all 13 manually authored semantic decision manifests.
- `procedure_review/corrections*.tsv`: all six correction/reconsideration manifests, including radiography, imaging, general surgery, dental and reviewed variants.

## Preparation and evidence outputs, preserved

| Artifact | Meaning |
|---|---|
| `mapping_procedure_final.before_review.csv` | Exact input backup |
| `groups.json` | Source/target groups, row membership, codes, score values, lexical evidence and priority tags |
| `procedures.json` | Eligible standard SNOMED Procedure metadata extracted from Athena |
| `targets.json` | Metadata for original automatic targets |
| `source_exact.json` | Source-name exact matches across eligible vocabulary concepts |
| `exact_replacement_candidates.json` | Result of the exact-alternative search; empty in this case |
| `vocabulary.sqlite` | Original preferred-name/synonym FTS5 index |
| `all_decisions.json` | Resolved group-level decisions and provenance |
| `review_audit.csv` | Full row-level old/new target and decision evidence |
| `flagged_review_queue.csv` | Unresolved mappings, with priorities first |
| `priority_review.csv` | Research-priority rows across statuses |
| `approved_etl_candidates.csv` | Approved rows in the Usagi schema |
| `review_run.json` | Counts, timestamp, checks and original/final hashes |
| `review_report.md` | Original report and limitations |
| `priority_ancestry_checks.json` | Actual anchor and Procedure-root checks |
| `mapping_procedure_final.reviewed.preview.csv` | Retained final snapshot copy of the preview |
| `../mapping_procedure_final.csv` | Final saved reviewed file |

`archive_inventory.json` is the definitive per-file list, size and hash. Temporary duplicate preview directories were not copied; their reproducible final outputs are preserved above. The archive contains 38 files, approximately 60.3 MB, plus its inventory. Licensed source Athena files are not part of the archive or portable plugin.

## Rebuild and validation commands

From the repository root:

```bash
python3 -m unittest discover -s mapping_with_agent/plugins/clinical-do-map/skills/do-map/tests -v
python3 mapping_with_agent/scripts/verify_archive.py mapping_with_agent/case-study/procedure-2026-09-16
python3 mapping_with_agent/scripts/case_helpers.py coverage
python3 mapping_with_agent/scripts/package.py
python3 mapping_with_agent/scripts/validate_package.py
```

See [VALIDATION.md](VALIDATION.md) for recorded results and [PUBLISH.md](PUBLISH.md) for public release steps.

The original hard-coded scripts are historical references. Use the new `do_map.py` and skill for future domains; do not copy the case's clinical mappings, reviewer label or score assumptions into a different source catalogue.
