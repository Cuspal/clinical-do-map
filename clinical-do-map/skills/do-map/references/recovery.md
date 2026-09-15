# Limits, recovery and maintenance

## Scope limits

The agent performs semantic review; the scripts do local retrieval, bookkeeping and structural validation. Tests cannot certify clinical correctness. Exact matches require explicit decisions in this generalized version. A reviewer label is attribution, not an expert credential.

CSV and tab-separated canonical exports are supported. XLSX, RF2, UMLS, OWL, FHIR terminology APIs and other distribution formats require a verified conversion step. No LLM API client, model key, patient-data upload or live database deployment is included. One-to-many mapping expansion and numeric/unit transformations require a separate ETL design.

A complete review may contain many flags. Flagged targets are not suitable accepted mappings simply because their IDs remain visible in the file. Broader approvals require attention to their lost detail and the study's needs.

## Resume ordinary work

Keep the run directory. Use `coverage` and `batches` with the existing decisions file; only pending, unprotected rows appear. Add decisions for new rows, or deliberately edit a previous record to revise it. Do not append a conflicting duplicate. Render to a new directory. A prepared run belongs to one immutable input and vocabulary index.

## When the input changed

If apply reports an external change, preserve both versions and compare against `baseline.csv`. Do not replace the expected hash just to make the command pass. Merge or create a fresh input and prepare a new run; carry forward reviewed meaning only after source/version/context checks. A live Usagi session can overwrite disk changes, so reopen its file after an external update.

## When a snapshot changed

Build a new index and prepare a new run. Re-check active/standard status, preferred-name changes, synonyms and hierarchy membership. A validity end date in an old snapshot does not establish current status in a newer terminology release. The as-of date and release are distinct.

## Interrupted apply

`apply.lock` indicates an active or interrupted writer. Confirm no writer is running before removing a stale lock. `pending_apply.json` records the intended source hash and artifact if the process stopped around replacement. Compare the actual source SHA256 with the receipt:

1. If it equals `mapped_sha256`, verify the preview hashes, then promote the pending receipt to `last_apply.json` and retain a recovery note.
2. If it equals `previous_sha256`, the replacement did not complete; preserve the pending receipt under a recovery filename, verify the preview, and retry.
3. If it equals neither, treat it as an external modification and reconcile manually.

Never automatically discard a pending receipt. The file replacement is atomic, but the CSV, audit directory, GUI state and filesystem receipts are not a single cross-application transaction. Backups and explicit recovery checks remain necessary.

## Prior reviewed data

Prior non-UNCHECKED rows are protected by default. Their decisions are counted as preserved, not newly reviewed. Invalid prior approved targets or inconsistent relationships stop rendering so they cannot silently enter a supposedly validated approved subset. Start a new run with `--review-existing` when those decisions are in scope.

## Installation and sharing

The portable plugin contains only instructions, scripts and synthetic fixtures. The accompanying historical case outside the plugin contains local catalogue/SNOMED-derived artifacts and must be treated under the source data and terminology licenses. Do not publish that archive as if it were unrestricted sample data. The original Athena downloads are not bundled.

Installers only write to a destination explicitly chosen by the operator, or the documented user skill folder. They refuse to overwrite an existing skill. Mapping itself does not install software, modify global agent instructions, or send messages.

After modifying the engine, run the synthetic integration tests and the skill/plugin validators. Check real behavior: stale hashes rejected, input preserved on failure, domain validity enforced, missing/duplicate decisions rejected, and complete output correct. Update the plugin version for an intentional release; host caches may require reinstalling and a new conversation.
