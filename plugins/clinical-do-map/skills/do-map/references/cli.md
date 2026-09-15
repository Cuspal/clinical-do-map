# CLI, configuration and decision schema

The helper uses Python 3.10+ and standard-library SQLite with FTS5. No API key, model client, database server or external package is needed. Python must provide the requested IANA timezone; if a platform lacks timezone data, use UTC or install its timezone database.

Examples assume a shell variable pointing to the installed skill:

```bash
MAPPING_TOOL="/absolute/path/to/do-map/scripts/do_map.py"
python3 "$MAPPING_TOOL" doctor
```

## Vocabulary preparation

```bash
python3 "$MAPPING_TOOL" index \
  --concepts /data/athena/CONCEPT.csv \
  --synonyms /data/athena/CONCEPT_SYNONYM.csv \
  --target SNOMED --domain Procedure \
  --as-of 2026-09-16 --vocab-version 'v5.0 27-AUG-25' \
  --out /data/reviews/snomed-procedure-20260916.sqlite
```

The date/version above belong to the historical example. For a new run, read the actual release and choose the current or intended as-of date. `--target RxNorm,RxNorm Extension` must be quoted as one shell argument because of the space; each comma-separated ID is literal. The same applies to multiple domains. Standard concepts are required unless `--include-nonstandard` is explicitly selected.

Athena's `.csv` files are commonly tab-separated. Both comma and tab exports are accepted; input encoding is UTF-8/UTF-8 BOM. The canonical concept table requires:

```text
concept_id,concept_name,domain_id,vocabulary_id,concept_class_id,
standard_concept,concept_code,valid_start_date,valid_end_date,invalid_reason
```

Dates use YYYYMMDD. Active records have empty `invalid_reason`; standard records have `standard_concept=S`. Identifiers are strings. For non-Athena tables, supply these fields or `--vocab-columns columns.json` mapping canonical field names to actual headers. This maps headers, not meaning or code-system semantics. The optional synonym table uses `concept_id,concept_synonym_name`; other columns are ignored.

Indexes are immutable and bind the selected vocabularies/domains/date/policy to file hashes. Reuse via `doctor --index path.sqlite`; a different release needs a new index. Large exports are streamed; the index retains selected vocabularies across domains for inspection, so disk use can be substantial. Only eligible terms enter candidate search.

## Run preparation

```bash
python3 "$MAPPING_TOOL" prepare \
  --input /data/mapping.csv --index /data/reviews/snomed-procedure-20260916.sqlite \
  --run /data/reviews/procedure-01 --reviewer Cuspal \
  --priorities /data/research/priorities.md --timezone Asia/Bangkok \
  --allow-target-changes --allow-wider
```

`--priorities -` deliberately means no priority document. `--priority-rules rules.json` adds deterministic navigation tags:

```json
{"rules":[{"tag":"stroke_reperfusion","pattern":"thrombol|thrombect|stroke"}]}
```

Read the document even when tags exist; keywords alone cannot implement it. Inspect patterns before use. A JSON priority document is still a document; rules are only loaded automatically from `--priority-rules`.

Input needs `sourceCode` and `sourceName`. Existing Usagi fields are recognized; missing review/target fields are appended to the rendered output. Source column aliases:

```json
{"sourceCode":"local_code","sourceName":"description","conceptId":"target_id","conceptName":"target_label"}
```

Pass this through `--columns`. The review fields are `mappingStatus`, `equivalence`, `statusSetBy`, `statusSetOn`, `comment`. Target fields are `conceptId`, `conceptName`, `domainId`; existing `conceptCode` and `vocabularyId` are also maintained when a target is approved/corrected. Unrelated columns survive unchanged. Existing `matchScore` is retained.

`--context-columns source_system,source_version` preserves disambiguating context in the queue/audit and in duplicate-code checks. Prior non-UNCHECKED rows are protected; `--review-existing` includes them in a new review. The flags `--allow-target-changes` and `--allow-wider` express review policies, not semantic evidence or a permission bypass.

## Work queues and search

```bash
python3 "$MAPPING_TOOL" batches --run /data/reviews/procedure-01 --size 50 --out /data/reviews/batches-01
python3 "$MAPPING_TOOL" search --index /data/reviews/snomed-procedure-20260916.sqlite --query 'intravenous thrombolysis'
python3 "$MAPPING_TOOL" search --index /data/reviews/snomed-procedure-20260916.sqlite --id 35621677
python3 "$MAPPING_TOOL" coverage --run /data/reviews/procedure-01
```

Search tokenizes and quotes the query before sending it to FTS; raw SQL/FTS syntax is not executed. Default search requires all words; `--any-word` widens retrieval. The rank is not confidence. Exact candidates in the queue are normalized-name evidence only. Codes themselves are never normalized.

Save decisions in the run's `decisions.jsonl`, or provide another file through `--decisions`. Each line is one object:

```json
{"row_ids":["r-copy-the-actual-id-from-the-queue"],"mapping_status":"APPROVED","equivalence":"EQUIVALENT","target_id":"35621677","rationale":"The source explicitly describes intravenous thrombolysis for stroke, matching the target route and cerebral arterial treatment.","evidence":["concept:35621677","local-catalogue:source-code-and-version"],"comment":""}
```

The row ID above is illustrative; actual IDs are generated from the input. A flag example:

```json
{"row_ids":["r-copy-the-actual-id-from-the-queue"],"mapping_status":"FLAGGED","equivalence":"UNREVIEWED","rationale":"The source does not specify imaging modality; the automatic CT target is not supported. Obtain the catalogue section or local definition.","evidence":["source:full-description-reviewed","local-vocabulary:CT-versus-MRI-candidates-checked"],"comment":"Clarify modality before mapping."}
```

Rules:

- Required: explicit nonempty `row_ids`, status, equivalence, rationale, evidence.
- `target_id` omitted: retain the current identifier. A string `"0"` explicitly clears it, requiring target-change authorization.
- `comment` is optional; flagged/WIDER rows get the rationale if comment is empty. Correction comments identify the old/new target and retained old score.
- Every new APPROVED decision must reference `concept:<target_id>` in evidence. Additional source/semantic evidence is expected from the agent. The tool checks reference presence, not whether the prose is clinically true.
- Multiple row IDs can share a decision only after each code/context was reviewed. Duplicate/stale/unknown row IDs are rejected.
- Only EQUAL/EQUIVALENT and explicitly permitted WIDER mappings can be newly approved. Other relations remain flagged.
- One target per row; no automatic one-to-many expansion. Record decomposition proposals in the rationale and flag insufficient single-target mappings.

## Validate, render and apply

```bash
python3 "$MAPPING_TOOL" render --run /data/reviews/procedure-01 \
  --complete --out /data/reviews/procedure-preview-01
python3 "$MAPPING_TOOL" apply --run /data/reviews/procedure-01 \
  --preview /data/reviews/procedure-preview-01
```

Rendering never changes the input or earlier output directories. Omitting `--complete` permits a progress render; it cannot be applied until every eligible row is decided. `apply` revalidates decisions, hashes, metadata and coverage, stages the result beside the source, and atomically replaces that file. Its timestamp is the exact preview's review timestamp; it is not regenerated during apply. Re-applying the identical result is a no-op.

Artifacts:

| File | Purpose |
|---|---|
| run/baseline.csv | Exact original bytes |
| run/config.json | Source/index hashes, vocabulary scope, policies and aliases |
| run/review_queue.jsonl | Immutable context-rich queue and stable row IDs |
| run/decisions.jsonl | Resumable, explicitly authored review decisions |
| preview/mapped.csv | Full reviewed mapping in the original schema plus needed fields |
| preview/approved.csv | Eligible approved subset, including documented broader mappings |
| preview/audit.csv | Original/new targets, source context, decisions and evidence |
| preview/flagged.csv | Unresolved/rejected mappings |
| preview/priority.csv | Tagged rows of all statuses |
| preview/decisions.snapshot.jsonl | Exact decisions used for this render |
| preview/manifest.json | Coverage, counts, hashes and timestamp |
| preview/report.md | Run summary and limitations |
| run/last_apply.json | Receipt identifying applied artifact and prior source hash |

CSV record numbers are data-record ordinals, not physical line numbers when quoted cells contain newlines. Output remains machine-readable; treat formula-like source text as untrusted if opening CSVs in a spreadsheet. Escaping it here would change the source data, so the mapper preserves it literally.

## Hierarchy checks

```bash
python3 "$MAPPING_TOOL" ancestry --ancestor-file /data/athena/CONCEPT_ANCESTOR.csv \
  --ids 4184832,35621677 --anchors 4216130,4145042 \
  --out /data/reviews/ancestry-checks.json
```

This checks each target/anchor pair in the supplied table. `--all-ancestors` also returns every listed ancestor for the selected targets. The command hashes the ancestry export. It does not assert that absence means clinical non-equivalence.
