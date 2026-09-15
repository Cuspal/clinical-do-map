#!/usr/bin/env python3
"""Local terminology review mechanics. No LLM calls or automatic approvals.

Python 3.10+, standard library, SQLite FTS5. See references/cli.md.
"""
import argparse
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import re
import sqlite3
import sys
import tempfile
from collections import Counter
from datetime import date, datetime, timezone
from urllib.parse import quote
from zoneinfo import ZoneInfo

VERSION = '1.0.0'
CONCEPT_FIELDS = ('concept_id', 'concept_name', 'domain_id', 'vocabulary_id',
                  'concept_class_id', 'standard_concept', 'concept_code',
                  'valid_start_date', 'valid_end_date', 'invalid_reason')
REVIEW_FIELDS = ('mappingStatus', 'equivalence', 'statusSetBy', 'statusSetOn', 'comment')
TARGET_FIELDS = ('conceptId', 'conceptName', 'domainId')
STATUSES = {'UNCHECKED', 'APPROVED', 'FLAGGED'}
EQUIVALENCES = {'EQUAL', 'EQUIVALENT', 'WIDER', 'NARROWER', 'INEXACT', 'UNMATCHED', 'UNREVIEWED'}


class MappingError(Exception):
    pass


def require(condition, message):
    if not condition:
        raise MappingError(message)


def sha_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha_file(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def normalized_name(value):
    # Retrieval only. Never apply to codes/units and never infer equivalence from it.
    return re.sub(r'\s+', ' ', value.casefold()).strip().rstrip('.')


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def read_table(path, delimiter=None):
    with Path(path).open(encoding='utf-8-sig', newline='') as f:
        if delimiter is None:
            header = f.readline()
            delimiter = '\t' if '\t' in header else ','
            f.seek(0)
        reader = csv.DictReader(f, delimiter=delimiter)
        require(reader.fieldnames and len(set(reader.fieldnames)) == len(reader.fieldnames), f'Invalid/duplicate headers: {path}')
        for n, row in enumerate(reader, 2):
            require(None not in row and all(v is not None for v in row.values()), f'Malformed CSV record {n}: {path}')
            yield row


def csv_data(rows, fields, delimiter=','):
    stream = io.StringIO(newline='')
    writer = csv.DictWriter(stream, fieldnames=fields, delimiter=delimiter, lineterminator='\r\n')
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode('utf-8')


def open_db(path):
    return sqlite3.connect('file:' + quote(str(Path(path).resolve()), safe='/') + '?mode=ro', uri=True)


def meta(db):
    return json.loads(db.execute('SELECT value FROM metadata WHERE key=?', ('index',)).fetchone()[0])


def concept(db, cid):
    found = db.execute('SELECT data,eligible FROM concepts WHERE id=?', (cid,)).fetchone()
    return dict(json.loads(found[0]), eligible=bool(found[1])) if found else None


def parse_day(text):
    try:
        return date.fromisoformat(text).strftime('%Y%m%d')
    except ValueError as e:
        raise MappingError('Dates must use YYYY-MM-DD') from e


def index_vocab(args):
    dest = Path(args.out).resolve()
    require(not dest.exists(), 'Index already exists; use a new path for a new vocabulary snapshot')
    day = parse_day(args.as_of)
    vocabularies = args.target.split(',')
    domains = args.domain.split(',')
    columns = read_json(args.vocab_columns) if args.vocab_columns else {}
    aliases = {f: columns.get(f, f) for f in CONCEPT_FIELDS}
    require(len(set(aliases.values())) == len(aliases), 'Vocabulary column aliases must be unique')
    dest.parent.mkdir(parents=True, exist_ok=True)
    temporary = dest.with_name(dest.name + '.building')
    require(not temporary.exists(), 'An unfinished index build exists; inspect or use a new output path')
    db = sqlite3.connect(temporary)
    count = eligible_count = term_count = 0
    concepts_hash = sha_file(args.concepts)
    synonyms_hash = sha_file(args.synonyms) if args.synonyms else None
    try:
        db.executescript('''
        CREATE TABLE concepts(id TEXT PRIMARY KEY, data TEXT NOT NULL, eligible INTEGER NOT NULL);
        CREATE TABLE exact_terms(norm TEXT, id TEXT, label TEXT, preferred INTEGER);
        CREATE VIRTUAL TABLE terms USING fts5(id UNINDEXED,label,preferred UNINDEXED);
        CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT);
        ''')
        for row in read_table(args.concepts):
            require(set(aliases.values()) <= row.keys(), 'Concept table is missing canonical fields; use --vocab-columns or normalize the export')
            c = {f: row[aliases[f]] for f in CONCEPT_FIELDS}
            cid = c['concept_id']
            require(cid and c['concept_name'], 'Concept IDs and names must not be empty')
            # Keep the selected vocabularies across domains/dates for rejected-target explanations.
            if c['vocabulary_id'] not in vocabularies:
                continue
            for field in ('valid_start_date', 'valid_end_date'):
                try:
                    datetime.strptime(c[field], '%Y%m%d')
                except ValueError as e:
                    raise MappingError(f'Invalid {field} for {cid}: {c[field]}') from e
            eligible = (c['domain_id'] in domains and not c['invalid_reason'] and
                        c['valid_start_date'] <= day <= c['valid_end_date'] and
                        (args.include_nonstandard or c['standard_concept'] == 'S'))
            db.execute('INSERT INTO concepts VALUES (?,?,?)', (cid, canonical(c), int(eligible)))
            count += 1
            if eligible:
                eligible_count += 1
                db.execute('INSERT INTO exact_terms VALUES (?,?,?,1)', (normalized_name(c['concept_name']), cid, c['concept_name']))
                db.execute('INSERT INTO terms VALUES (?,?,1)', (cid, c['concept_name']))
                term_count += 1
        require(eligible_count > 0, 'No eligible concepts. Check vocabulary IDs, domain, standard status and snapshot date')
        if args.synonyms:
            for row in read_table(args.synonyms):
                require({'concept_id', 'concept_synonym_name'} <= row.keys(), 'Synonyms require concept_id and concept_synonym_name')
                c = db.execute('SELECT eligible FROM concepts WHERE id=?', (row['concept_id'],)).fetchone()
                if not c or not c[0] or not row['concept_synonym_name']:
                    continue
                label = row['concept_synonym_name']
                db.execute('INSERT INTO exact_terms VALUES (?,?,?,0)', (normalized_name(label), row['concept_id'], label))
                db.execute('INSERT INTO terms VALUES (?,?,0)', (row['concept_id'], label))
                term_count += 1
        db.execute('CREATE INDEX terms_exact ON exact_terms(norm)')
        db.execute('CREATE INDEX terms_concept ON exact_terms(id)')
        require(sha_file(args.concepts) == concepts_hash, 'Concept export changed during indexing')
        require(not args.synonyms or sha_file(args.synonyms) == synonyms_hash, 'Synonym export changed during indexing')
        info = {'engine_version': VERSION, 'target': vocabularies, 'domain': domains,
                'as_of': args.as_of, 'require_standard': not args.include_nonstandard,
                'vocabulary_version': args.vocab_version, 'concepts_path': str(Path(args.concepts).resolve()),
                'concepts_sha256': concepts_hash, 'synonyms_sha256': synonyms_hash,
                'concept_count': count, 'eligible_count': eligible_count, 'term_count': term_count}
        db.execute('INSERT INTO metadata VALUES (?,?)', ('index', canonical(info)))
        db.commit()
        db.close()
        temporary.replace(dest)
        return info
    except BaseException:
        db.close()
        # Only the incomplete file created by this invocation is removed.
        temporary.unlink(missing_ok=True)
        raise


def search(args):
    with open_db(args.index) as db:
        if args.id:
            c = concept(db, args.id)
            return {'concept': c, 'terms': [r[0] for r in db.execute('SELECT label FROM exact_terms WHERE id=?', (args.id,))]}
        words = re.findall(r'\w+', args.query or '', flags=re.UNICODE)
        require(words, 'Provide a nonempty --query or --id')
        query = (' OR ' if args.any_word else ' AND ').join('"' + w + '"' for w in words)
        found = []
        seen = set()
        for cid, label, score in db.execute('SELECT id,label,bm25(terms) FROM terms WHERE terms MATCH ? ORDER BY bm25(terms) LIMIT ?', (query, args.limit * 30)):
            if cid in seen:
                continue
            seen.add(cid)
            found.append({'concept': concept(db, cid), 'matched_term': label, 'retrieval_rank_score': score})
            if len(found) == args.limit:
                break
        return {'query': args.query, 'results': found, 'note': 'Search ranks are retrieval aids, not calibrated confidence or approval.'}


def input_csv(path):
    data = Path(path).read_bytes()
    text = data.decode('utf-8-sig')
    first = text.splitlines()[0] if text else ''
    delimiter = '\t' if '\t' in first else ','
    with io.StringIO(text, newline='') as f:
        fields = next(csv.reader(f, delimiter=delimiter), [])
    reader = csv.DictReader(io.StringIO(text, newline=''), delimiter=delimiter)
    require(fields and len(set(fields)) == len(fields), 'Invalid/duplicate source headers')
    rows = list(reader)
    require(all(None not in r and all(v is not None for v in r.values()) for r in rows), 'Malformed source CSV')
    require(rows, 'Input mapping is empty')
    return data, fields, rows, delimiter


def prepare(args):
    run = Path(args.run).resolve()
    require(not run.exists(), 'Run exists. Resume with batches/coverage/render; do not prepare over it')
    data, fields, rows, delimiter = input_csv(args.input)
    columns = read_json(args.columns) if args.columns else {}
    require(set(columns) <= set(REVIEW_FIELDS + TARGET_FIELDS + ('sourceCode', 'sourceName', 'matchScore', 'conceptCode', 'vocabularyId')), 'Unknown source column mapping role')
    names = {f: columns.get(f, f) for f in REVIEW_FIELDS + TARGET_FIELDS + ('sourceCode', 'sourceName', 'matchScore', 'conceptCode', 'vocabularyId')}
    require(len(set(names.values())) == len(names), 'Source column aliases must be unique')
    require({names['sourceCode'], names['sourceName']} <= set(fields), 'Input requires sourceCode/sourceName or explicit --columns aliases')
    context = args.context_columns.split(',') if args.context_columns else []
    require(set(context) <= set(fields), 'A context column does not exist in the input')
    require(not (set(context) & {names[f] for f in REVIEW_FIELDS + TARGET_FIELDS}), 'Context cannot use mutable review/target fields')
    ZoneInfo(args.timezone)
    require(args.reviewer.strip(), 'Reviewer attribution is required')
    rules = read_json(args.priority_rules) if args.priority_rules else {'rules': []}
    if args.priority_rules:
        require(isinstance(rules, dict) and isinstance(rules.get('rules'), list), 'Priority rules require {"rules":[...]}')
    compiled = [(r['tag'], re.compile(r['pattern'], re.I)) for r in rules['rules']]
    priority_bytes = Path(args.priorities).read_bytes() if args.priorities != '-' else b''
    digest = sha_bytes(data)
    queue = []
    with open_db(args.index) as db:
        index_meta = meta(db)
        for number, row in enumerate(rows, 1):
            code, name = row[names['sourceCode']], row[names['sourceName']]
            status = row.get(names['mappingStatus'], '') or 'UNCHECKED'
            require(status in STATUSES, f'Unknown source status at record {number}: {status}')
            cid = row.get(names['conceptId'], '') or '0'
            exact = [dict(concept_id=x[0], matched_term=x[1], preferred=bool(x[2])) for x in db.execute('SELECT DISTINCT id,label,preferred FROM exact_terms WHERE norm=?', (normalized_name(name),))] if name.strip() else []
            ctx = {k: row[k] for k in context}
            row_id = 'r-' + sha_bytes((digest + ':' + str(number) + ':' + canonical(row)).encode())[:24]
            group_id = 'g-' + sha_bytes(canonical([normalized_name(name), cid, ctx]).encode())[:20]
            queue.append({'row_id': row_id, 'record_number': number, 'group_id': group_id,
                          'source_code': code, 'source_name': name, 'context': ctx,
                          'original_target_id': cid, 'original_target': concept(db, cid),
                          'original_status': status, 'match_score': row.get(names['matchScore'], ''),
                          'priority_tags': [tag for tag, regex in compiled if regex.search(name)],
                          'exact_candidates': exact, 'protected_prior_review': status != 'UNCHECKED' and not args.review_existing})
    # Copies and checks finish before the run is exposed as prepared.
    run.mkdir(parents=True)
    (run / 'baseline.csv').write_bytes(data)
    (run / 'priorities.snapshot').write_bytes(priority_bytes)
    queue_payload = ''.join(canonical(r) + '\n' for r in queue).encode('utf-8')
    config = {'engine_version': VERSION, 'source_path': str(Path(args.input).resolve()),
              'baseline_sha256': digest, 'index_path': str(Path(args.index).resolve()),
              'queue_sha256': sha_bytes(queue_payload),
              'index_sha256': sha_file(args.index), 'index_metadata': index_meta,
              'reviewer': args.reviewer, 'timezone': args.timezone, 'allow_target_changes': args.allow_target_changes,
              'allow_wider': args.allow_wider, 'review_existing': args.review_existing,
              'columns': names, 'original_fields': fields, 'delimiter': delimiter, 'context_columns': context,
              'priority_sha256': sha_bytes(priority_bytes), 'priority_rules': rules, 'row_count': len(rows)}
    write_json(run / 'config.json', config)
    (run / 'review_queue.jsonl').write_bytes(queue_payload)
    (run / 'decisions.jsonl').write_text('', encoding='utf-8')
    return {'run': str(run), 'rows': len(rows), 'protected': sum(q['protected_prior_review'] for q in queue),
            'priority_rows': sum(bool(q['priority_tags']) for q in queue),
            'rows_with_exact_candidates': sum(bool(q['exact_candidates']) for q in queue),
            'note': 'No approvals generated. Read the priority snapshot and review each eligible row.'}


def read_jsonl(path):
    for number, line in enumerate(Path(path).read_text(encoding='utf-8').splitlines(), 1):
        if line.strip():
            try:
                yield json.loads(line)
            except json.JSONDecodeError as e:
                raise MappingError(f'Invalid JSONL {path}:{number}: {e}') from e


def load_run(run):
    run = Path(run).resolve()
    config = read_json(run / 'config.json')
    require(sha_file(run / 'baseline.csv') == config['baseline_sha256'], 'Baseline hash mismatch')
    require(sha_file(config['index_path']) == config['index_sha256'], 'Vocabulary index changed; prepare a new run')
    require(sha_file(run / 'priorities.snapshot') == config['priority_sha256'], 'Priority snapshot changed')
    require(sha_file(run / 'review_queue.jsonl') == config['queue_sha256'], 'Immutable review queue changed')
    queue = list(read_jsonl(run / 'review_queue.jsonl'))
    data, fields, rows, delimiter = input_csv(run / 'baseline.csv')
    require(fields == config['original_fields'] and delimiter == config['delimiter'], 'Baseline schema mismatch')
    require(len(queue) == len(rows) == config['row_count'], 'Queue/baseline coverage mismatch')
    names = config['columns']
    for i, (q, row) in enumerate(zip(queue, rows), 1):
        expected = 'r-' + sha_bytes((config['baseline_sha256'] + ':' + str(i) + ':' + canonical(row)).encode())[:24]
        require(q['row_id'] == expected and q['record_number'] == i, 'Queue row identity or ordering changed')
        require(q['source_name'] == row[names['sourceName']] and q['source_code'] == row[names['sourceCode']], 'Queue source content changed')
        require(q['original_target_id'] == (row.get(names['conceptId'], '') or '0'), 'Queue target content changed')
        prior = row.get(names['mappingStatus'], '') or 'UNCHECKED'
        require(q['protected_prior_review'] == (prior != 'UNCHECKED' and not config['review_existing']), 'Queue protection changed')
    return config, queue, rows


def read_decisions(path, queue):
    decisions = {}
    known = {q['row_id']: q for q in queue}
    for d in read_jsonl(path):
        require(isinstance(d, dict), 'Each decision must be an object')
        require(set(d) <= {'row_ids', 'mapping_status', 'equivalence', 'target_id', 'rationale', 'evidence', 'comment'}, 'Unknown decision fields')
        require(isinstance(d.get('row_ids'), list) and d['row_ids'], 'Decision requires explicit row_ids')
        require(d.get('mapping_status') in {'APPROVED', 'FLAGGED'}, 'Decision must be APPROVED or FLAGGED')
        require(d.get('equivalence') in EQUIVALENCES, 'Invalid equivalence value')
        require(isinstance(d.get('rationale'), str) and d['rationale'].strip(), 'Every decision requires a substantive rationale')
        require(isinstance(d.get('evidence'), list) and d['evidence'] and all(isinstance(e, str) and e.strip() for e in d['evidence']), 'Evidence must be a nonempty list of reference strings')
        require('target_id' not in d or isinstance(d['target_id'], str), 'Target ID must be a string, including "0" for no target')
        require('comment' not in d or isinstance(d['comment'], str), 'Comment must be a string')
        for rid in d['row_ids']:
            require(rid in known, f'Stale or unknown row_id: {rid}')
            require(rid not in decisions, f'Duplicate/conflicting decision for {rid}; edit the original decision')
            require(not known[rid]['protected_prior_review'], f'Prior review is protected: {rid}; a new --review-existing run is required')
            decisions[rid] = d
    return decisions


def coverage(config, queue, decisions):
    protected = sum(q['protected_prior_review'] for q in queue)
    return {'rows': len(queue), 'protected_prior_reviews': protected, 'explicit_decisions': len(decisions),
            'pending': len(queue) - protected - len(decisions),
            'decision_statuses': dict(Counter(d['mapping_status'] for d in decisions.values()))}


def batches(args):
    config, queue, _ = load_run(args.run)
    decisions = read_decisions(args.decisions or Path(args.run) / 'decisions.jsonl', queue)
    result = coverage(config, queue, decisions)
    if args.out:
        dest = Path(args.out)
        require(not dest.exists(), 'Batch destination already exists')
        dest.mkdir(parents=True)
        pending = [q for q in queue if not q['protected_prior_review'] and q['row_id'] not in decisions]
        pending.sort(key=lambda q: (not bool(q['priority_tags']), q['record_number']))
        for start in range(0, len(pending), args.size):
            (dest / f'batch-{start // args.size + 1:04d}.jsonl').write_text(''.join(canonical(q) + '\n' for q in pending[start:start + args.size]), encoding='utf-8')
    return result


def render_rows(config, queue, originals, decisions, timestamp):
    names = config['columns']
    fields = list(config['original_fields'])
    for role in REVIEW_FIELDS + TARGET_FIELDS:
        if names[role] not in fields:
            fields.append(names[role])
    mutable = {names[k] for k in REVIEW_FIELDS + TARGET_FIELDS}
    mutable |= {names[k] for k in ('conceptCode', 'vocabularyId') if names[k] in fields}
    mapped, audit = [], []
    with open_db(config['index_path']) as db:
        for q, original in zip(queue, originals):
            row = {f: original.get(f, '') for f in fields}
            d = decisions.get(q['row_id'])
            old_id = q['original_target_id']
            new_id = d.get('target_id', old_id) if d else old_id
            target = concept(db, new_id)
            changed = old_id != new_id
            if d:
                status, eq = d['mapping_status'], d['equivalence']
                require(not changed or config['allow_target_changes'], 'Target changes not enabled for this run')
                if changed and new_id not in ('', '0'):
                    require(target and target['eligible'], f'Corrected target is not eligible: {new_id}')
                if status == 'APPROVED':
                    require(eq in {'EQUAL', 'EQUIVALENT', 'WIDER'}, 'Narrower/inexact/unresolved mappings cannot be approved by this workflow')
                    require(eq != 'WIDER' or config['allow_wider'], 'WIDER approval requires --allow-wider at prepare')
                    require(target and target['eligible'], f'Approved target not active/in-scope/standard: {new_id}')
                    require(q['source_name'].strip(), 'An empty source description cannot be approved')
                    require('concept:' + new_id in d['evidence'], f'Approved mapping must reference concept:{new_id} in evidence')
                comment = d.get('comment', '')
                if status == 'FLAGGED' or eq == 'WIDER':
                    comment = comment or d['rationale']
                if changed:
                    comment = f'Corrected target {old_id} to {new_id}. {comment or d["rationale"]}'
                    if original.get(names['matchScore'], ''):
                        comment += ' Original matchScore retained for the previous automatic suggestion.'
                row.update({names['mappingStatus']: status, names['equivalence']: eq,
                            names['statusSetBy']: config['reviewer'], names['statusSetOn']: timestamp,
                            names['comment']: comment})
                # Canonicalize metadata for every approved or explicitly corrected target.
                if status == 'APPROVED' or changed:
                    if not config['allow_target_changes'] and target:
                        for role, field in [('conceptName', 'concept_name'), ('domainId', 'domain_id'),
                                            ('conceptCode', 'concept_code'), ('vocabularyId', 'vocabulary_id')]:
                            if names[role] in original:
                                require(original[names[role]] == target[field], 'Target metadata needs correction; target-change policy is not enabled')
                    row[names['conceptId']] = new_id
                    row[names['conceptName']] = target['concept_name'] if target else ''
                    row[names['domainId']] = target['domain_id'] if target else ''
                    for role, field in [('conceptCode', 'concept_code'), ('vocabularyId', 'vocabulary_id')]:
                        if names[role] in fields:
                            row[names[role]] = target[field] if target else ''
                basis = 'explicit_review'
            elif q['protected_prior_review']:
                status = row[names['mappingStatus']]
                eq = row[names['equivalence']]
                require(eq in EQUIVALENCES, 'Preserved prior review has invalid equivalence; re-review it')
                if status == 'APPROVED':
                    require(target and target['eligible'], 'A prior approved target is now ineligible. Start a --review-existing run')
                    require(eq in {'EQUAL', 'EQUIVALENT', 'WIDER'}, 'A prior approval has an unresolved or narrower relationship; re-review it')
                    for role, field in [('conceptName', 'concept_name'), ('domainId', 'domain_id'),
                                        ('conceptCode', 'concept_code'), ('vocabularyId', 'vocabulary_id')]:
                        if names[role] in original:
                            require(original[names[role]] == target[field], 'Prior approved target metadata is stale; re-review it')
                        elif names[role] in fields:
                            row[names[role]] = target[field]
                basis = 'preserved_prior_review'
            else:
                status, eq, basis = 'UNCHECKED', 'UNREVIEWED', 'pending'
                row[names['mappingStatus']], row[names['equivalence']] = status, eq
            for field in config['original_fields']:
                require(field in mutable or row[field] == original[field], f'Unauthorized column change: {field}')
            mapped.append(row)
            audit.append({'row_id': q['row_id'], 'record_number': q['record_number'],
                          'sourceCode': q['source_code'], 'sourceName': q['source_name'],
                          'context': canonical(q['context']), 'priorityTags': ';'.join(q['priority_tags']),
                          'originalTargetId': old_id, 'originalTargetName': original.get(names['conceptName'], ''),
                          'targetId': new_id, 'targetName': target['concept_name'] if target else '',
                          'targetVocabulary': target['vocabulary_id'] if target else '',
                          'targetDomain': target['domain_id'] if target else '',
                          'targetCode': target['concept_code'] if target else '',
                          'targetChanged': str(changed).lower(), 'mappingStatus': status, 'equivalence': eq,
                          'basis': basis, 'matchScore': q['match_score'],
                          'rationale': d['rationale'] if d else '', 'evidence': canonical(d['evidence']) if d else '[]',
                          'statusSetBy': row[names['statusSetBy']], 'statusSetOn': row[names['statusSetOn']]})
    # Code-only lookup conflicts cannot silently enter the approved subset.
    code_targets = {}
    for a in audit:
        if a['mappingStatus'] != 'APPROVED':
            continue
        key = (a['sourceCode'], a['context'])
        require(key not in code_targets or code_targets[key] == a['targetId'], 'Conflicting approved targets for the same source code/context; resolve the source namespace or bundle')
        code_targets[key] = a['targetId']
    return mapped, fields, audit


def render(args):
    run = Path(args.run).resolve()
    out = Path(args.out).resolve()
    require(not out.exists(), 'Render destination exists; use a new directory to preserve prior artifacts')
    config, queue, originals = load_run(run)
    decision_path = Path(args.decisions or run / 'decisions.jsonl')
    decisions = read_decisions(decision_path, queue)
    cov = coverage(config, queue, decisions)
    require(not args.complete or cov['pending'] == 0, f'Incomplete review: {cov["pending"]} pending rows')
    now = datetime.now(timezone.utc)
    stamp = str(int(now.timestamp() * 1000))
    mapped, fields, audit = render_rows(config, queue, originals, decisions, stamp)
    payload = csv_data(mapped, fields, config['delimiter'])
    reread = list(csv.DictReader(io.StringIO(payload.decode()), delimiter=config['delimiter']))
    require(mapped == reread, 'CSV roundtrip failed')
    stats = dict(Counter(a['mappingStatus'] for a in audit))
    manifest = {'engine_version': VERSION, 'run_path': str(run), 'coverage': cov, 'status_counts': stats,
                'review_time_utc': now.isoformat(), 'review_time_local': now.astimezone(ZoneInfo(config['timezone'])).isoformat(),
                'status_timestamp_ms': stamp, 'baseline_sha256': config['baseline_sha256'],
                'config_sha256': sha_file(run / 'config.json'), 'queue_sha256': sha_file(run / 'review_queue.jsonl'),
                'index_sha256': config['index_sha256'], 'decisions_sha256': sha_file(decision_path),
                'mapped_sha256': sha_bytes(payload), 'target_changes': sum(a['targetChanged'] == 'true' for a in audit),
                'approved_wider': sum(a['mappingStatus'] == 'APPROVED' and a['equivalence'] == 'WIDER' for a in audit),
                'vocabulary': config['index_metadata'], 'attribution': config['reviewer'],
                'attribution_note': 'Reviewer label is attribution; it is not independent human clinical sign-off.',
                'duplicate_source_codes': len(queue) - len({q['source_code'] for q in queue})}
    out.mkdir(parents=True)
    (out / 'mapped.csv').write_bytes(payload)
    (out / 'decisions.snapshot.jsonl').write_bytes(decision_path.read_bytes())
    audit_fields = list(audit[0])
    for filename, selected in [('audit.csv', audit), ('flagged.csv', [a for a in audit if a['mappingStatus'] == 'FLAGGED']),
                               ('priority.csv', [a for a in audit if a['priorityTags']])]:
        (out / filename).write_bytes(csv_data(selected, audit_fields))
    # Include only validated approvals; this is source mapping format, not an OMOP table export.
    approved = [r for r in mapped if r[config['columns']['mappingStatus']] == 'APPROVED']
    (out / 'approved.csv').write_bytes(csv_data(approved, fields, config['delimiter']))
    write_json(out / 'manifest.json', manifest)
    report = f'''# Terminology mapping review\n\nTarget: {', '.join(config['index_metadata']['target'])}; domain: {', '.join(config['index_metadata']['domain'])}.\n\nSnapshot: {config['index_metadata']['vocabulary_version']}; eligibility as of {config['index_metadata']['as_of']}.\n\n## Coverage\n\n- Rows: {cov['rows']}\n- Explicit decisions: {cov['explicit_decisions']}\n- Preserved prior reviews: {cov['protected_prior_reviews']}\n- Pending: {cov['pending']}\n- Status counts: {canonical(stats)}\n- Corrected targets: {manifest['target_changes']}\n- Approved WIDER mappings: {manifest['approved_wider']}\n\nReviewer attribution: {config['reviewer']}; timestamp: {manifest['review_time_local']}. This does not assert independent human clinical sign-off.\n\n## Interpretation\n\nWIDER means the target is broader than the source; omitted detail is documented. FLAGGED targets are not approved for ETL. UNREVIEWED plus FLAGGED means an inspected but unresolved mapping; UNCHECKED means work remains. Exact labels and retrieval scores did not generate approvals.\n\nThe priority snapshot is in the run directory. Priority tags aid navigation and are not phenotype definitions. Codes alone do not establish indications, timing thresholds, death, readmission or causal outcomes. Check hierarchy coverage for your selected anchors.\n\n`approved.csv` is a validated subset in the input schema, not a CDM SOURCE_TO_CONCEPT_MAP export. Duplicate source codes: {manifest['duplicate_source_codes']}. Use the configured source context columns when joining. Vocabulary IDs and concept IDs remain strings.\n\n## Evidence\n\nSee audit.csv, flagged.csv, priority.csv, decisions.snapshot.jsonl and manifest.json. All original non-review/non-target fields and row order are preserved. All approved and corrected targets passed this snapshot's eligibility checks. Full semantic correctness remains the responsibility of the reviewer; scripts validate structure and evidence presence, not clinical meaning.\n'''
    (out / 'report.md').write_text(report, encoding='utf-8')
    return manifest


def apply_review(args):
    run = Path(args.run).resolve()
    preview = Path(args.preview).resolve()
    lock = run / 'apply.lock'
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as e:
        raise MappingError('Another apply or interrupted apply owns apply.lock; inspect it before resuming') from e
    os.close(fd)
    temporary = None
    try:
        config, queue, originals = load_run(run)
        manifest = read_json(preview / 'manifest.json')
        require(manifest['run_path'] == str(run), 'Preview belongs to another run')
        for field, path in [('config_sha256', run / 'config.json'), ('queue_sha256', run / 'review_queue.jsonl'),
                            ('decisions_sha256', preview / 'decisions.snapshot.jsonl'), ('mapped_sha256', preview / 'mapped.csv')]:
            require(sha_file(path) == manifest[field], f'Stale/modified preview: {field}')
        require(manifest['index_sha256'] == config['index_sha256'] and manifest['baseline_sha256'] == config['baseline_sha256'], 'Preview vocabulary/baseline mismatch')
        decisions = read_decisions(preview / 'decisions.snapshot.jsonl', queue)
        require(coverage(config, queue, decisions)['pending'] == 0, 'Cannot apply an incomplete review')
        mapped, fields, _ = render_rows(config, queue, originals, decisions, manifest['status_timestamp_ms'])
        content = csv_data(mapped, fields, config['delimiter'])
        require(sha_bytes(content) == manifest['mapped_sha256'], 'Recomputed mapping differs from reviewed preview')
        source = Path(config['source_path'])
        require(not source.is_symlink(), 'Apply does not follow source symlinks; prepare from the real path')
        allowed = {config['baseline_sha256']}
        receipt_path = run / 'last_apply.json'
        if receipt_path.exists():
            receipt = read_json(receipt_path)
            require(receipt['baseline_sha256'] == config['baseline_sha256'], 'Prior apply receipt belongs to another baseline')
            allowed.add(receipt['mapped_sha256'])
        current = sha_file(source)
        require(current in allowed, 'Source changed externally (possibly a live Usagi session). Reconcile before apply')
        if current == manifest['mapped_sha256']:
            return {'applied': False, 'reason': 'Identical review already present', 'source': str(source)}
        receipt = {'baseline_sha256': config['baseline_sha256'], 'previous_sha256': current,
                   'mapped_sha256': manifest['mapped_sha256'], 'preview': str(preview), 'source': str(source),
                   'applied_at': datetime.now(timezone.utc).isoformat()}
        # Pending receipt makes a process crash between replacement and receipt recoverable.
        pending = run / 'pending_apply.json'
        require(not pending.exists(), 'An interrupted apply has a pending receipt; inspect before retrying')
        with tempfile.NamedTemporaryFile(dir=source.parent, prefix='.do-map-', suffix='.tmp', delete=False) as f:
            temporary = Path(f.name)
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(temporary, source.stat().st_mode & 0o777)
        require(sha_file(source) == current, 'Source changed while preparing replacement')
        write_json(pending, receipt)
        os.replace(temporary, source)
        temporary = None
        require(sha_file(source) == manifest['mapped_sha256'], 'Applied file hash mismatch')
        pending.replace(receipt_path)
        return dict(receipt, applied=True)
    finally:
        if temporary:
            temporary.unlink(missing_ok=True)
        lock.unlink(missing_ok=True)


def ancestry(args):
    targets, anchors = set(args.ids.split(',')), set(args.anchors.split(','))
    rows = {k: [] for k in targets}
    for r in read_table(args.ancestor_file):
        require({'ancestor_concept_id', 'descendant_concept_id', 'min_levels_of_separation', 'max_levels_of_separation'} <= r.keys(), 'Unsupported ancestry table schema')
        if r['descendant_concept_id'] in targets and (args.all_ancestors or r['ancestor_concept_id'] in anchors):
            rows[r['descendant_concept_id']].append(r)
    result = {'ancestor_file_sha256': sha_file(args.ancestor_file), 'checks': [
        {'target_id': target, 'anchor_id': anchor, 'listed': any(r['ancestor_concept_id'] == anchor for r in rows[target])}
        for target in sorted(targets) for anchor in sorted(anchors)], 'relationships': rows,
        'note': 'An absent edge is not proof of clinical non-equivalence. Explicitly include relevant targets when hierarchy expansion misses them.'}
    if args.out:
        require(not Path(args.out).exists(), 'Ancestry output already exists')
        write_json(args.out, result)
    return result


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='command', required=True)
    s = sub.add_parser('doctor', help='Check Python and SQLite FTS5')
    s.add_argument('--index')
    s = sub.add_parser('index', help='Build an immutable local vocabulary index')
    for flag in ('concepts', 'target', 'domain', 'as-of', 'vocab-version', 'out'):
        s.add_argument('--' + flag, required=True)
    s.add_argument('--synonyms')
    s.add_argument('--vocab-columns')
    s.add_argument('--include-nonstandard', action='store_true')
    s = sub.add_parser('search', help='Search eligible concepts or inspect a concept by ID')
    s.add_argument('--index', required=True)
    s.add_argument('--query')
    s.add_argument('--id')
    s.add_argument('--any-word', action='store_true')
    s.add_argument('--limit', type=int, default=10)
    s = sub.add_parser('prepare', help='Back up input and prepare a row-level review queue')
    for flag in ('input', 'index', 'run', 'reviewer', 'priorities'):
        s.add_argument('--' + flag, required=True)
    s.add_argument('--priority-rules')
    s.add_argument('--columns')
    s.add_argument('--context-columns', default='')
    s.add_argument('--timezone', default='UTC')
    s.add_argument('--allow-target-changes', action='store_true')
    s.add_argument('--allow-wider', action='store_true')
    s.add_argument('--review-existing', action='store_true')
    for name in ('batches', 'coverage'):
        s = sub.add_parser(name)
        s.add_argument('--run', required=True)
        s.add_argument('--decisions')
        s.add_argument('--out')
        s.add_argument('--size', type=int, default=50)
    s = sub.add_parser('render', help='Validate and generate a reviewable output without changing the input')
    for flag in ('run', 'out'):
        s.add_argument('--' + flag, required=True)
    s.add_argument('--decisions')
    s.add_argument('--complete', action='store_true')
    s = sub.add_parser('apply', help='Apply a complete validated preview with source hash protection')
    for flag in ('run', 'preview'):
        s.add_argument('--' + flag, required=True)
    s = sub.add_parser('ancestry', help='Check supplied OMOP ancestor edges; never infer clinical meaning')
    for flag in ('ancestor-file', 'ids', 'anchors'):
        s.add_argument('--' + flag, required=True)
    s.add_argument('--all-ancestors', action='store_true')
    s.add_argument('--out')
    return p


def main(argv=None):
    args = parser().parse_args(argv)
    if hasattr(args, 'size'):
        require(args.size > 0, 'Batch size must be positive')
    if hasattr(args, 'limit'):
        require(1 <= args.limit <= 100, 'Search limit must be 1-100')
    if args.command == 'doctor':
        with sqlite3.connect(':memory:') as db:
            db.execute('CREATE VIRTUAL TABLE t USING fts5(label)')
        result = {'python': sys.version.split()[0], 'sqlite': sqlite3.sqlite_version, 'fts5': True, 'engine_version': VERSION}
        if args.index:
            with open_db(args.index) as db:
                result['index'] = meta(db)
    else:
        fn = {'index': index_vocab, 'search': search, 'prepare': prepare, 'batches': batches, 'coverage': batches,
              'render': render, 'apply': apply_review, 'ancestry': ancestry}[args.command]
        result = fn(args)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    try:
        main()
    except (MappingError, OSError, sqlite3.Error, ValueError, KeyError, TypeError) as error:
        print(f'ERROR: {error}', file=sys.stderr)
        sys.exit(2)
