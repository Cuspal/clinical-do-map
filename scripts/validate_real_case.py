#!/usr/bin/env python3
"""Replay archived judgments through the generic engine in an isolated output.

This is structural regression validation, not a new clinical review. The source
mapping and archived evidence are read-only; no apply command is invoked.
"""
import argparse
import contextlib
import csv
import importlib.util
import io
import json
from pathlib import Path
import shutil
import sqlite3
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / 'plugins/clinical-do-map/skills/do-map'
spec = importlib.util.spec_from_file_location('mapping_engine', SKILL / 'scripts/do_map.py')
engine = importlib.util.module_from_spec(spec)
spec.loader.exec_module(engine)


def call(*args):
    stream = io.StringIO()
    with contextlib.redirect_stdout(stream):
        engine.main([str(a) for a in args])
    return json.loads(stream.getvalue())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case', type=Path, default=ROOT / 'case-study/procedure-2026-09-16')
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    work = args.case / 'mapping_usagi_final/procedure_review'
    out = args.out.resolve()
    if out.exists():
        parser.exit(2, 'Validation output exists; use a new directory\n')
    out.mkdir(parents=True)
    baseline = work / 'mapping_procedure_final.before_review.csv'
    baseline_hash = engine.sha_file(baseline)
    concepts = json.loads((work / 'procedures.json').read_text())
    concept_path = out / 'derived_concepts.csv'
    concept_path.write_bytes(engine.csv_data(concepts.values(), engine.CONCEPT_FIELDS))
    synonym_path = out / 'derived_synonyms.csv'
    db = sqlite3.connect('file:' + quote(str((work / 'vocabulary.sqlite').resolve()), safe='/') + '?mode=ro', uri=True)
    with synonym_path.open('w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['concept_id', 'concept_synonym_name'])
        writer.writerows(db.execute('SELECT concept_id,name FROM terms WHERE preferred=0'))
    db.close()
    index = out / 'index.sqlite'
    indexed = call('index', '--concepts', concept_path, '--synonyms', synonym_path, '--target', 'SNOMED',
                   '--domain', 'Procedure', '--as-of', '2026-09-16', '--vocab-version', 'Derived from archived Athena v5.0 27-AUG-25 Procedure evidence', '--out', index)
    source = out / 'input.copy.csv'
    shutil.copy2(baseline, source)
    run = out / 'run'
    prepared = call('prepare', '--input', source, '--index', index, '--run', run,
                    '--reviewer', 'Structural replay of archived Cuspal judgments',
                    '--priorities', SKILL / 'assets/procedure_priorities.md',
                    '--priority-rules', SKILL / 'assets/procedure_priority_rules.json',
                    '--timezone', 'Asia/Bangkok', '--allow-target-changes', '--allow-wider')
    queue = list(engine.read_jsonl(run / 'review_queue.jsonl'))
    groups = {g['id']: g for g in json.loads((work / 'groups.json').read_text())}
    old_decisions = json.loads((work / 'all_decisions.json').read_text())
    replay = []
    for d in old_decisions:
        g = groups[d['groupId']]
        replay.append({'row_ids': [queue[i]['row_id'] for i in g['rows']],
                       'mapping_status': d['mappingStatus'], 'equivalence': d['equivalence'],
                       'target_id': d['reviewedConceptId'], 'rationale': d['rationale'],
                       'evidence': ['archive:all_decisions.json#group-' + str(d['groupId']),
                                    'concept:' + d['reviewedConceptId']], 'comment': ''})
    (run / 'decisions.jsonl').write_text(''.join(json.dumps(d) + '\n' for d in replay))
    result = call('render', '--run', run, '--out', out / 'preview', '--complete')
    original_result = json.loads((work / 'review_run.json').read_text())
    engine.require(result['status_counts'] == original_result['statusCounts'], 'Replay status counts differ')
    engine.require(result['target_changes'] == original_result['targetChangedRows'], 'Replay target-change counts differ')
    expected = list(engine.read_table(args.case / 'mapping_usagi_final/mapping_procedure_final.csv'))
    actual = list(engine.read_table(out / 'preview/mapped.csv'))
    for a, b in zip(expected, actual):
        for field in ('sourceCode', 'sourceName', 'conceptId', 'mappingStatus', 'equivalence', 'matchScore'):
            engine.require(a[field] == b[field], 'Replay disagreement: ' + a['sourceCode'] + '/' + field)
    engine.require(len(expected) == len(actual), 'Replay row count differs')
    engine.require(engine.sha_file(baseline) == baseline_hash == engine.sha_file(source), 'Read-only validation changed its input')
    summary = {'kind': 'structural replay; archived semantic judgments were reused, not independently re-reviewed',
               'rows': len(actual), 'eligible_concepts': indexed['eligible_count'],
               'status_counts': result['status_counts'], 'target_changes': result['target_changes'],
               'coverage': result['coverage'], 'input_unchanged': True,
               'compared_fields': ['sourceCode', 'sourceName', 'conceptId', 'mappingStatus', 'equivalence', 'matchScore'],
               'expected_comment_timestamp_differences': True, 'source_archive': str(args.case.resolve())}
    engine.write_json(out / 'validation_result.json', summary)
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
