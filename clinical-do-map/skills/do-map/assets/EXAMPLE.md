# A synthetic first run

The `demo_*` CSVs contain invented labels and IDs. They test the workflow without licensed vocabulary or patient data. Copy `demo_source.csv` into a new working directory before applying a review; do not mutate the installed skill's assets.

Use the agent command with explicit canonical input rather than Athena:

```text
/do-map SYNTHETIC Procedure /path/to/do-map/assets/demo_priorities.md --input /new/work/demo_source.csv --concepts /path/to/do-map/assets/demo_concepts.csv --vocab-version synthetic-demo-1 --as-of 2026-09-16 --reviewer Demo --out /new/work/review --correct-targets
```

In Codex, use `$do-map` instead. Expected interpretation: alpha maps to DEMO-P1, beta's wrong automatic alpha target is corrected to DEMO-P2, and the unspecified service remains flagged. The 0.99 score on beta must not lead to approval of alpha. The agent must create the actual row-bound JSONL decisions; no production score rule is embedded in the sample.

The helper sequence is `doctor → index → prepare → batches/search → decisions → coverage → render --complete`. Omitting `--apply` from the agent request delivers a reviewed copy. Inspect the result before deciding whether to update your disposable source.

For real work, replace the synthetic vocabulary, file, domain, date, release and priorities. The adjacent `procedure_priorities.md` and `procedure_priority_rules.json` reproduce the original study's prioritization, not universal priorities for other domains.
