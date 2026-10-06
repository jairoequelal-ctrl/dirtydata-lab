import copy
import json
from pathlib import Path
import tempfile
import unittest
from dirtydata_lab.core import generate, detect, evaluate, read_csv, ERRORS, PROFILES

class DirtyDataTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_byte_reproducibility(self):
        generate(self.root / 'a', seed=42)
        generate(self.root / 'b', seed=42)
        for a in (self.root / 'a').iterdir():
            self.assertEqual(a.read_bytes(), (self.root / 'b' / a.name).read_bytes())

    def test_seed_changes_dataset(self):
        a = generate(self.root / 'a', seed=1)
        b = generate(self.root / 'b', seed=2)
        self.assertNotEqual(a['hashes']['dirty.csv'], b['hashes']['dirty.csv'])

    def test_all_error_types_present(self):
        truth = generate(self.root, rows=100, rate=.2)
        self.assertEqual({e['error_type'] for e in truth['events']}, set(ERRORS))
        self.assertEqual(truth['event_count'], 20)
        self.assertEqual(truth['dirty_rows'], 103)

    def test_clean_data_passes_contract(self):
        for profile in PROFILES:
            folder = self.root / profile
            generate(folder, profile=profile)
            contract = json.loads((folder / 'contract.json').read_text())
            self.assertEqual(detect(read_csv(folder / 'clean.csv'), contract), [])

    def test_baseline_matches_fixture_across_profiles_and_seeds(self):
        for profile in PROFILES:
            for seed in range(10):
                folder = self.root / profile
                truth = generate(folder, rows=40, rate=.6, seed=seed, profile=profile)
                contract = json.loads((folder / 'contract.json').read_text())
                result = evaluate(truth, detect(read_csv(folder / 'dirty.csv'), contract))
                self.assertEqual(result['f1'], 1.0)
                self.assertEqual(result['false_positives'], 0)

    def test_ground_truth_reverses_every_mutation(self):
        truth = generate(self.root)
        dirty = {r['row_id']: r for r in read_csv(self.root / 'dirty.csv')}
        for event in reversed(truth['events']):
            self.assertEqual(dirty[event['row_id']], event['after'])
            if event['operation'] == 'append':
                del dirty[event['row_id']]
            else:
                dirty[event['row_id']] = event['before']
        self.assertEqual(list(dirty.values()), read_csv(self.root / 'clean.csv'))

    def test_duplicate_rows_have_unique_benchmark_locators(self):
        truth = generate(self.root, errors=['duplicate_id'], rows=10, rate=1)
        data = read_csv(self.root / 'dirty.csv')
        self.assertEqual(len({r['row_id'] for r in data}), 20)
        self.assertEqual(len(truth['events']), 10)
        self.assertTrue(all(r['customer_id'] == data[0]['customer_id'] for r in data[10:]))

    def test_error_subset(self):
        truth = generate(self.root, errors=['invalid_date'], rate=.5)
        self.assertEqual({e['error_type'] for e in truth['events']}, {'invalid_date'})

    def test_invalid_configuration(self):
        cases = [{'rows': 1}, {'rows': True}, {'rate': -1}, {'rate': float('nan')},
                 {'rate': 2}, {'profile': 'unknown'}, {'errors': []},
                 {'errors': ['unknown']}, {'errors': ['invalid_date', 'invalid_date']},
                 {'errors': ['invalid_date'], 'rate': 1}, {'seed': True}]
        for case in cases:
            with self.subTest(case=case), self.assertRaises(ValueError):
                generate(self.root, **case)

    def test_zero_event_budget(self):
        truth = generate(self.root, rate=0)
        self.assertEqual(truth['events'], [])
        self.assertEqual((self.root / 'clean.csv').read_bytes(), (self.root / 'dirty.csv').read_bytes())
        result = evaluate(truth, [])
        self.assertEqual(result['f1'], 0)
        self.assertEqual(result['false_negatives'], 0)

    def test_metrics_with_false_positives_and_misses(self):
        truth = generate(self.root, rows=10, rate=.2)
        good = {k: truth['events'][0][k] for k in ['row_id', 'column', 'error_type']}
        false = {'row_id': 'R999999', 'column': 'signup_date', 'error_type': 'invalid_date'}
        result = evaluate(truth, [good, good, false])
        self.assertEqual(result['true_positives'], 1)
        self.assertEqual(result['false_positives'], 1)
        self.assertEqual(result['false_negatives'], 1)
        self.assertEqual(result['precision'], .5)
        self.assertEqual(result['recall'], .5)
        self.assertEqual(result['prediction_count'], 3)
        self.assertEqual(result['unique_prediction_count'], 2)

    def test_wrong_column_is_not_a_detection(self):
        truth = generate(self.root, rows=10, rate=.1)
        e = truth['events'][0]
        result = evaluate(truth, [{'row_id': e['row_id'], 'column': 'wrong', 'error_type': e['error_type']}])
        self.assertEqual((result['false_positives'], result['false_negatives']), (1, 1))

    def test_invalid_predictions_fail_explicitly(self):
        truth = generate(self.root)
        for pred in [{}, [None], [{'row_id': 1, 'column': 'x', 'error_type': 'missing_value'}],
                     [{'row_id': 'R1', 'column': 'x', 'error_type': 'typo'}]]:
            with self.assertRaises(ValueError):
                evaluate(truth, pred)

    def test_row_locators_are_checked(self):
        path = self.root / 'invalid.csv'
        for content in ['row_id,name\nR1,x\nR1,y\n', 'row_id,name\n,x\n',
                        'row_id,name\nR1,x,y\n', 'name\nx\n']:
            path.write_text(content)
            with self.assertRaises(ValueError):
                read_csv(path)

if __name__ == '__main__':
    unittest.main()
