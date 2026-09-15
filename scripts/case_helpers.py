#!/usr/bin/env python3
"""Read-only consolidation of exploratory lookups used in the original case."""
import argparse
import json
from pathlib import Path
import re
import sqlite3
from collections import Counter
from urllib.parse import quote

DEFAULT = Path(__file__).resolve().parents[1] / 'case-study/procedure-2026-09-16'


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('command', choices=['group', 'search', 'coverage'])
    p.add_argument('--case', type=Path, default=DEFAULT)
    p.add_argument('--group-id', type=int)
    p.add_argument('--query')
    p.add_argument('--limit', type=int, default=10)
    args = p.parse_args()
    work = args.case / 'mapping_usagi_final/procedure_review'
    groups = json.loads((work / 'groups.json').read_text())
    decisions = json.loads((work / 'all_decisions.json').read_text())
    if args.command == 'group':
        if not args.group_id or not 1 <= args.group_id <= len(groups):
            p.error('--group-id must be an existing group number')
        result = {'source_group': groups[args.group_id - 1],
                  'review_decision': next(d for d in decisions if d['groupId'] == args.group_id)}
    elif args.command == 'coverage':
        explicit = {}
        duplicates = []
        for path in sorted(work.glob('decisions_*.tsv')):
            for line in path.read_text().splitlines():
                if not line or line.startswith('#'):
                    continue
                ids, code, rationale = line.split('|', 2)
                for gid in map(int, ids.split(',')):
                    if gid in explicit:
                        duplicates.append(gid)
                    explicit[gid] = code
        missing = [g['id'] for g in groups if not g['lexical_evidence'] and g['id'] not in explicit]
        result = {'groups': len(groups), 'explicit_semantic_groups': len(explicit), 'duplicates': duplicates,
                  'missing_semantic_decisions': missing, 'lexical_groups': dict(Counter(g['lexical_evidence'] for g in groups)),
                  'recorded_run': json.loads((work / 'review_run.json').read_text())}
    else:
        words = re.findall(r'\w+', args.query or '')
        if not words or not 1 <= args.limit <= 100:
            p.error('Provide --query and --limit between 1 and 100')
        query = ' AND '.join('"' + w + '"' for w in words)
        concepts = json.loads((work / 'procedures.json').read_text())
        db = sqlite3.connect('file:' + quote(str((work / 'vocabulary.sqlite').resolve()), safe='/') + '?mode=ro', uri=True)
        seen, result = set(), []
        for cid, label in db.execute('SELECT concept_id,name FROM terms WHERE terms MATCH ? ORDER BY bm25(terms) LIMIT ?', (query, args.limit * 30)):
            if cid in seen:
                continue
            seen.add(cid)
            result.append({'concept': concepts[cid], 'matched_term': label})
            if len(result) == args.limit:
                break
        db.close()
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
