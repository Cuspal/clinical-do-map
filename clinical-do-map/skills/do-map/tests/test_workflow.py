"""Synthetic integration tests. These verify mechanics, not clinical correctness."""
import contextlib
import csv
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'do_map.py'
spec = importlib.util.spec_from_file_location('do_map', SCRIPT)
engine = importlib.util.module_from_spec(spec)
spec.loader.exec_module(engine)


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='do-map-test-')
        self.root = Path(self.temp.name)
        self.addCleanup(self.temp.cleanup)
        self.concepts = self.root / 'concepts.csv'
        labels = [
            ('P1', 'Synthetic procedure alpha', 'Procedure', 'S', '', '20000101', '20991231'),
            ('P2', 'Synthetic procedure beta', 'Procedure', 'S', '', '20000101', '20991231'),
            ('C1', 'Synthetic condition', 'Condition', 'S', '', '20000101', '20991231'),
            ('D1', 'Synthetic drug 10 mg oral tablet', 'Drug', 'S', '', '20000101', '20991231'),
            ('M1', 'Synthetic serum measurement', 'Measurement', 'S', '', '20000101', '20991231'),
            ('U1', 'Synthetic unit mM', 'Unit', 'S', '', '20000101', '20991231'),
            ('OLD', 'Synthetic inactive procedure', 'Procedure', 'S', 'D', '20000101', '20250101'),
            ('FUT', 'Synthetic future procedure', 'Procedure', 'S', '', '20300101', '20991231'),
            ('NS', 'Synthetic nonstandard procedure', 'Procedure', '', '', '20000101', '20991231'),
        ]
        rows = [dict(zip(engine.CONCEPT_FIELDS, (cid, name, domain, 'SYNTH', 'Test', standard, cid, start, end, invalid)))
                for cid, name, domain, standard, invalid, start, end in labels]
        self.concepts.write_bytes(engine.csv_data(rows, engine.CONCEPT_FIELDS))
        self.synonyms = self.root / 'synonyms.csv'
        self.synonyms.write_text('concept_id,concept_synonym_name\nP1,Synthetic alpha synonym\n')
        self.index = self.root / 'index.sqlite'
        self.call('index', '--concepts', self.concepts, '--synonyms', self.synonyms,
                  '--target', 'SYNTH', '--domain', 'Procedure', '--as-of', '2026-09-16',
                  '--vocab-version', 'synthetic-test-1', '--out', self.index)
        self.priorities = self.root / 'priorities.md'
        self.priorities.write_text('Prioritize beta, but review alpha too. No outcome inference.')
        self.rules = self.root / 'rules.json'
        self.rules.write_text(json.dumps({'rules': [{'tag': 'beta_priority', 'pattern': 'beta'}]}))
        self.source = self.root / 'mapping.csv'
        self.fields = ['sourceCode', 'sourceName', 'matchScore', 'mappingStatus', 'equivalence',
                       'statusSetBy', 'statusSetOn', 'conceptId', 'conceptName', 'domainId',
                       'comment', 'createdBy', 'createdOn', 'sourceSystem']
        self.rows = [
            ['001', 'Synthetic alpha synonym', '0.99', 'UNCHECKED', 'UNREVIEWED', '', '0', 'P1', 'Synthetic procedure alpha', 'Procedure', '', '<auto>', '123', 'A'],
            ['002', 'Synthetic beta; excludes alpha', '0.99', 'UNCHECKED', 'UNREVIEWED', '', '0', 'P1', 'Synthetic procedure alpha', 'Procedure', '', '<auto>', '123', 'A'],
            ['003', 'Ambiguous "term", with\nnewline Ω', '0.12', 'UNCHECKED', 'UNREVIEWED', '', '0', '0', 'Unmapped', '', '', '<auto>', '123', 'A'],
        ]
        self.write_source()
        self.run = self.root / 'run'

    def call(self, *args):
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream):
            engine.main([str(a) for a in args])
        return json.loads(stream.getvalue())

    def write_source(self):
        self.source.write_bytes(engine.csv_data([dict(zip(self.fields, r)) for r in self.rows], self.fields))

    def prepare(self, *extra):
        return self.call('prepare', '--input', self.source, '--index', self.index, '--run', self.run,
                         '--priorities', self.priorities, '--priority-rules', self.rules,
                         '--reviewer', 'Synthetic Reviewer', '--timezone', 'UTC', *extra)

    def decisions(self, *, wider=False):
        queue = list(engine.read_jsonl(self.run / 'review_queue.jsonl'))
        result = []
        for q in queue:
            n = q['record_number']
            d = {'row_ids': [q['row_id']], 'mapping_status': 'FLAGGED' if n == 3 else 'APPROVED',
                 'equivalence': 'UNREVIEWED' if n == 3 else 'WIDER' if wider and n == 1 else 'EQUIVALENT',
                 'rationale': 'Explicit synthetic semantic review; source context inspected.',
                 'evidence': ['source:synthetic-fixture'], 'comment': ''}
            if n != 3:
                d['target_id'] = 'P1' if n == 1 else 'P2'
                d['evidence'].append('concept:' + d['target_id'])
            result.append(d)
        self.save_decisions(result)
        return result

    def save_decisions(self, records):
        (self.run / 'decisions.jsonl').write_text(''.join(json.dumps(d) + '\n' for d in records))

    def render(self, name='preview', complete=True):
        return self.call('render', '--run', self.run, '--out', self.root / name, *(['--complete'] if complete else []))

    def test_index_scope_dates_and_search(self):
        data = self.call('doctor', '--index', self.index)
        self.assertEqual(data['index']['eligible_count'], 2)
        for cid in ('OLD', 'FUT', 'C1', 'NS'):
            self.assertFalse(self.call('search', '--index', self.index, '--id', cid)['concept']['eligible'])
        match = self.call('search', '--index', self.index, '--query', 'synthetic alpha synonym')
        self.assertEqual(match['results'][0]['concept']['concept_id'], 'P1')
        self.call('search', '--index', self.index, '--query', 'x-ray " OR 1=1; DROP TABLE concepts;')
        self.assertTrue(self.call('search', '--index', self.index, '--id', 'P1')['concept']['eligible'])

    def test_exact_and_high_score_never_approve_automatically(self):
        before = self.source.read_bytes()
        stats = self.prepare()
        self.assertEqual(stats['rows_with_exact_candidates'], 1)
        cov = self.call('coverage', '--run', self.run)
        self.assertEqual(cov['explicit_decisions'], 0)
        self.assertEqual(cov['pending'], 3)
        with self.assertRaises(engine.MappingError):
            self.render()
        self.assertEqual(before, self.source.read_bytes())

    def test_complete_roundtrip_corrected_target_and_apply(self):
        before = self.source.read_bytes()
        self.prepare('--allow-target-changes')
        self.decisions()
        preview = self.render()
        self.assertEqual(preview['status_counts'], {'APPROVED': 2, 'FLAGGED': 1})
        self.assertEqual(preview['target_changes'], 1)
        self.assertEqual(before, self.source.read_bytes())
        rows = list(engine.read_table(self.root / 'preview/mapped.csv'))
        self.assertEqual(rows[1]['conceptId'], 'P2')
        self.assertIn('previous automatic suggestion', rows[1]['comment'])
        self.assertEqual(rows[0]['comment'], '')
        self.assertEqual(rows[0]['sourceCode'], '001')
        self.assertEqual(rows[2]['sourceName'], self.rows[2][1])
        for old, new in zip(self.rows, rows):
            for field in ('sourceCode', 'sourceName', 'matchScore', 'createdBy', 'createdOn', 'sourceSystem'):
                self.assertEqual(old[self.fields.index(field)], new[field])
        self.call('apply', '--run', self.run, '--preview', self.root / 'preview')
        self.assertEqual(engine.sha_file(self.source), preview['mapped_sha256'])
        self.assertEqual(before, (self.run / 'baseline.csv').read_bytes())
        again = self.call('apply', '--run', self.run, '--preview', self.root / 'preview')
        self.assertFalse(again['applied'])

    def test_resume_skips_completed_rows_and_priority_first(self):
        self.prepare('--allow-target-changes')
        decisions = self.decisions()
        self.save_decisions(decisions[:1])
        stats = self.call('batches', '--run', self.run, '--out', self.root / 'batches', '--size', '1')
        self.assertEqual(stats['pending'], 2)
        first = next(engine.read_jsonl(self.root / 'batches/batch-0001.jsonl'))
        self.assertEqual(first['source_code'], '002')
        progress = self.render(complete=False)
        self.assertEqual(progress['coverage']['pending'], 2)
        with self.assertRaises(engine.MappingError):
            self.call('apply', '--run', self.run, '--preview', self.root / 'preview')

    def test_wrong_domain_inactive_future_nonstandard_approvals_rejected(self):
        self.prepare('--allow-target-changes')
        decisions = self.decisions()
        for cid in ('C1', 'OLD', 'FUT', 'NS', 'missing'):
            decisions[0]['target_id'] = cid
            decisions[0]['evidence'] = ['concept:' + cid]
            self.save_decisions(decisions)
            with self.assertRaises(engine.MappingError, msg=cid):
                self.render(name='bad-' + cid)

    def test_duplicate_stale_missing_evidence_and_narrower_rejected(self):
        self.prepare('--allow-target-changes')
        ds = self.decisions()
        self.save_decisions(ds + ds[:1])
        with self.assertRaises(engine.MappingError):
            self.call('coverage', '--run', self.run)
        ds[0]['row_ids'] = ['r-from-another-baseline']
        self.save_decisions(ds)
        with self.assertRaises(engine.MappingError):
            self.call('coverage', '--run', self.run)
        ds = self.decisions()
        ds[0]['evidence'] = []
        self.save_decisions(ds)
        with self.assertRaises(engine.MappingError):
            self.render()
        ds = self.decisions()
        ds[0]['equivalence'] = 'NARROWER'
        self.save_decisions(ds)
        with self.assertRaises(engine.MappingError):
            self.render()

    def test_target_and_wider_policy(self):
        self.prepare()
        self.decisions()
        with self.assertRaises(engine.MappingError):
            self.render()
        # Use a second run with corrected-target permission but no broader-approval policy.
        self.run = self.root / 'run2'
        self.prepare('--allow-target-changes')
        self.decisions(wider=True)
        with self.assertRaises(engine.MappingError):
            self.render()
        self.run = self.root / 'run3'
        self.prepare('--allow-target-changes', '--allow-wider')
        self.decisions(wider=True)
        self.assertEqual(self.render()['approved_wider'], 1)

    def test_external_source_edit_and_modified_preview_rejected(self):
        self.prepare('--allow-target-changes')
        self.decisions()
        self.render()
        self.source.write_bytes(self.source.read_bytes() + b'\n')
        external = self.source.read_bytes()
        with self.assertRaises(engine.MappingError):
            self.call('apply', '--run', self.run, '--preview', self.root / 'preview')
        self.assertEqual(external, self.source.read_bytes())
        self.source.write_bytes((self.run / 'baseline.csv').read_bytes())
        (self.root / 'preview/mapped.csv').write_text('tampered')
        with self.assertRaises(engine.MappingError):
            self.call('apply', '--run', self.run, '--preview', self.root / 'preview')

    def test_baseline_index_and_queue_integrity(self):
        self.prepare()
        baseline = (self.run / 'baseline.csv').read_bytes()
        (self.run / 'baseline.csv').write_bytes(baseline + b'\n')
        with self.assertRaises(engine.MappingError):
            self.call('coverage', '--run', self.run)
        (self.run / 'baseline.csv').write_bytes(baseline)
        queue = (self.run / 'review_queue.jsonl').read_bytes()
        (self.run / 'review_queue.jsonl').write_bytes(queue + b'\n')
        with self.assertRaises(engine.MappingError):
            self.call('coverage', '--run', self.run)
        (self.run / 'review_queue.jsonl').write_bytes(queue)
        with self.index.open('ab') as f:
            f.write(b'changed-index')
        with self.assertRaises(engine.MappingError):
            self.call('coverage', '--run', self.run)

    def test_existing_reviews_preserved_and_not_counted_as_new(self):
        self.rows[0][3:7] = ['APPROVED', 'EQUAL', 'Prior Reviewer', '1000']
        self.write_source()
        self.prepare('--allow-target-changes')
        ds = self.decisions()
        with self.assertRaises(engine.MappingError):
            self.call('coverage', '--run', self.run)
        self.save_decisions(ds[1:])
        result = self.render()
        self.assertEqual(result['coverage']['protected_prior_reviews'], 1)
        self.assertEqual(result['coverage']['explicit_decisions'], 2)
        rows = list(engine.read_table(self.root / 'preview/mapped.csv'))
        self.assertEqual(rows[0]['statusSetBy'], 'Prior Reviewer')
        self.assertEqual(rows[0]['statusSetOn'], '1000')

    def test_duplicate_code_conflict_and_namespace_context(self):
        self.rows[1][0] = self.rows[0][0]
        self.rows[1][-1] = 'B'
        self.write_source()
        self.prepare('--allow-target-changes')
        self.decisions()
        with self.assertRaises(engine.MappingError):
            self.render()
        self.run = self.root / 'run-with-context'
        self.prepare('--allow-target-changes', '--context-columns', 'sourceSystem')
        self.decisions()
        self.assertEqual(self.render()['duplicate_source_codes'], 1)

    def test_generic_input_and_non_procedure_domains(self):
        for domain, cid, label in [('Drug', 'D1', 'Synthetic drug 10 mg oral tablet'),
                                    ('Measurement', 'M1', 'Synthetic serum measurement'),
                                    ('Condition', 'C1', 'Synthetic condition'), ('Unit', 'U1', 'Synthetic unit mM')]:
            index = self.root / (domain + '.sqlite')
            self.call('index', '--concepts', self.concepts, '--target', 'SYNTH', '--domain', domain,
                      '--as-of', '2026-09-16', '--vocab-version', 'synthetic-test-1', '--out', index)
            source = self.root / (domain + '.csv')
            source.write_bytes(engine.csv_data([{'code': '001-mM', 'label': label, 'context': 'retained'}], ['code', 'label', 'context']))
            aliases = self.root / 'aliases.json'
            aliases.write_text(json.dumps({'sourceCode': 'code', 'sourceName': 'label'}))
            run = self.root / ('run-' + domain)
            self.call('prepare', '--input', source, '--index', index, '--run', run, '--columns', aliases,
                      '--reviewer', 'Synthetic Reviewer', '--priorities', '-', '--allow-target-changes')
            q = next(engine.read_jsonl(run / 'review_queue.jsonl'))
            decision = {'row_ids': [q['row_id']], 'mapping_status': 'APPROVED', 'equivalence': 'EQUAL',
                        'target_id': cid, 'rationale': 'Synthetic source semantics inspected for this domain.',
                        'evidence': ['concept:' + cid]}
            (run / 'decisions.jsonl').write_text(json.dumps(decision) + '\n')
            self.call('render', '--run', run, '--out', self.root / ('preview-' + domain), '--complete')
            row = next(engine.read_table(self.root / ('preview-' + domain) / 'mapped.csv'))
            self.assertEqual(row['domainId'], domain)
            self.assertEqual(row['code'], '001-mM')
            self.assertEqual(row['context'], 'retained')

    def test_ancestry_presence_and_absence(self):
        path = self.root / 'ancestors.tsv'
        path.write_text('ancestor_concept_id\tdescendant_concept_id\tmin_levels_of_separation\tmax_levels_of_separation\nROOT\tP1\t1\t2\n')
        result = self.call('ancestry', '--ancestor-file', path, '--ids', 'P1,P2', '--anchors', 'ROOT')
        self.assertEqual([c['listed'] for c in result['checks']], [True, False])

    def test_stale_target_metadata_requires_target_permission(self):
        self.rows[0][8] = 'Stale target label'
        self.write_source()
        self.prepare()
        ds = self.decisions()
        ds[1]['mapping_status'] = 'FLAGGED'
        ds[1]['equivalence'] = 'UNREVIEWED'
        ds[1].pop('target_id')
        self.save_decisions(ds)
        with self.assertRaises(engine.MappingError):
            self.render()
        self.run = self.root / 'run-with-permission'
        self.prepare('--allow-target-changes')
        self.decisions()
        self.render()
        row = next(engine.read_table(self.root / 'preview/mapped.csv'))
        self.assertEqual(row['conceptName'], 'Synthetic procedure alpha')

    def test_apply_lock_and_pending_receipt_preserve_input(self):
        self.prepare('--allow-target-changes')
        self.decisions()
        self.render()
        before = self.source.read_bytes()
        (self.run / 'apply.lock').write_text('simulated active writer')
        with self.assertRaises(engine.MappingError):
            self.call('apply', '--run', self.run, '--preview', self.root / 'preview')
        self.assertTrue((self.run / 'apply.lock').exists())
        (self.run / 'apply.lock').unlink()
        (self.run / 'pending_apply.json').write_text('{}')
        with self.assertRaises(engine.MappingError):
            self.call('apply', '--run', self.run, '--preview', self.root / 'preview')
        self.assertEqual(before, self.source.read_bytes())
        self.assertTrue((self.run / 'pending_apply.json').exists())


if __name__ == '__main__':
    unittest.main()
