"""Synthetic generator, transparent rule baseline and strict event-level evaluation."""
from collections import Counter
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
import csv
import hashlib
import html
import json
import math
from pathlib import Path
import random

ERRORS = ('missing_value', 'duplicate_id', 'invalid_date', 'negative_amount',
          'invalid_category', 'extra_whitespace', 'leading_zero_loss', 'orphan_reference')
PROFILES = {
    'customers': {'id': 'customer_id', 'name': 'customer_name', 'amount': 'credit_limit',
                  'date': 'signup_date', 'fk': 'account_manager_id'},
    'products': {'id': 'sku', 'name': 'product_name', 'amount': 'price',
                 'date': 'release_date', 'fk': 'supplier_id'},
    'payments': {'id': 'payment_id', 'name': 'merchant_name', 'amount': 'amount',
                 'date': 'posted_at', 'fk': 'customer_id'},
}


def dump_json(path, obj):
    Path(path).write_text(json.dumps(obj, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def write_csv(path, rows, fields=None):
    fields = fields or list(rows[0])
    with Path(path).open('w', newline='', encoding='utf-8') as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path):
    with Path(path).open(newline='', encoding='utf-8-sig') as file:
        reader = csv.DictReader(file)
        headers = reader.fieldnames or []
        if len(headers) != len(set(headers)):
            raise ValueError('Duplicate CSV headers')
        rows = list(reader)
    if not rows or 'row_id' not in headers:
        raise ValueError('CSV needs at least one record and a row_id column')
    if any(None in row or any(v is None for v in row.values()) for row in rows):
        raise ValueError('Malformed CSV row')
    ids = [r['row_id'] for r in rows]
    if any(not x for x in ids) or len(set(ids)) != len(ids):
        raise ValueError('row_id must be nonempty and unique; it is a benchmark locator')
    return rows


def generate(output='output', rows=100, seed=42, rate=0.2, profile='customers', errors=None):
    """Write a labeled challenge. Rate budgets events, not corrupted-cell proportion."""
    if isinstance(rows, bool) or not isinstance(rows, int) or rows < 2:
        raise ValueError('rows must be an integer >= 2')
    if not isinstance(seed, int) or isinstance(seed, bool):
        raise ValueError('seed must be an integer')
    if not isinstance(rate, (float, int)) or not math.isfinite(rate) or not 0 <= rate <= 1:
        raise ValueError('rate must be finite and between 0 and 1')
    if profile not in PROFILES:
        raise ValueError(f'Unknown profile: {profile}')
    kinds = list(ERRORS if errors is None else errors)
    if not kinds or len(kinds) != len(set(kinds)) or any(x not in ERRORS for x in kinds):
        raise ValueError('Choose a nonempty unique subset of supported errors')
    p = PROFILES[profile]
    rng = random.Random(seed)
    parent_ids = [f'P{i:03}' for i in range(1, 11)]
    categories = ['standard', 'premium', 'enterprise']
    clean = []
    for i in range(rows):
        clean.append({'row_id': f'R{i + 1:06}', p['id']: f'{profile[:3].upper()}-{i + 1:06}',
                      p['name']: f'Demo {profile[:-1]} {i + 1:06}',
                      'email': f'demo{i + 1}@example.invalid',
                      p['amount']: f'{rng.randrange(100, 100000) / 100:.2f}',
                      p['date']: (date(2025, 1, 1) + timedelta(days=rng.randrange(365))).isoformat(),
                      'category': rng.choice(categories), 'postal_code': f'0{rng.randrange(1000, 10000)}',
                      p['fk']: rng.choice(parent_ids)})
    dirty = [dict(r) for r in clean]
    count = math.floor(rows * rate)
    schedule = [kinds[i % len(kinds)] for i in range(count)]
    # With n events at rate=1, at least one must be a duplicate so row 0 can be
    # protected as a stable duplicate source. Otherwise reject impossible budgets.
    mutations = sum(k != 'duplicate_id' for k in schedule)
    if mutations > rows - 1:
        raise ValueError('This error selection needs a lower rate: row 0 is reserved as a clean source')
    indices = list(range(1, rows))
    rng.shuffle(indices)
    selected = iter(indices)
    events = []
    for kind in schedule:
        if kind == 'duplicate_id':
            before = None
            record = dict(clean[0])
            record['row_id'] = f'R{len(dirty) + 1:06}'
            dirty.append(record)
            column = p['id']
        else:
            record = dirty[next(selected)]
            before = dict(record)
            if kind == 'missing_value':
                column = p['name']; record[column] = ''
            elif kind == 'invalid_date':
                column = p['date']; record[column] = '2025-02-30'
            elif kind == 'negative_amount':
                column = p['amount']; record[column] = '-' + record[column]
            elif kind == 'invalid_category':
                column = 'category'; record[column] = 'premiun'
            elif kind == 'extra_whitespace':
                column = p['name']; record[column] = '  ' + record[column] + '  '
            elif kind == 'leading_zero_loss':
                column = 'postal_code'; record[column] = record[column].lstrip('0')
            else:
                column = p['fk']; record[column] = 'UNKNOWN-PARENT'
        events.append({'row_id': record['row_id'], 'column': column, 'error_type': kind,
                       'operation': 'append' if before is None else 'update',
                       'before': before, 'after': dict(record)})
    folder = Path(output)
    folder.mkdir(parents=True, exist_ok=True)
    fields = list(clean[0])
    write_csv(folder / 'clean.csv', clean)
    write_csv(folder / 'dirty.csv', dirty)
    write_csv(folder / 'parents.csv', [{'parent_id': x} for x in parent_ids])
    contract = {'profile': profile, 'fields': p, 'required_columns': fields,
                'categories': categories, 'parent_ids': parent_ids,
                'postal_code_regex': '^0[0-9]{4}$', 'amount_min': '0.00'}
    dump_json(folder / 'contract.json', contract)
    hashes = {name: hashlib.sha256((folder / name).read_bytes()).hexdigest()
              for name in ['clean.csv', 'dirty.csv', 'parents.csv', 'contract.json']}
    truth = {'schema_version': 1, 'generator_version': '0.1.0', 'seed': seed,
             'base_rows': rows, 'dirty_rows': len(dirty), 'requested_event_rate': rate,
             'event_count': len(events), 'errors': kinds, 'hashes': hashes, 'events': events}
    dump_json(folder / 'ground_truth.json', truth)
    dump_json(folder / 'starter_predictions.json', [])
    make_report(folder / 'report.html', truth)
    return truth


def make_report(path, truth):
    counts = Counter(e['error_type'] for e in truth['events'])
    rows = ''.join(f'<tr><td>{html.escape(k)}</td><td>{counts[k]}</td></tr>' for k in ERRORS)
    samples = ''.join('<tr>' + ''.join(f'<td>{html.escape(str(e[k]))}</td>'
                      for k in ['row_id', 'column', 'error_type', 'operation']) + '</tr>'
                      for e in truth['events'][:15])
    body = f'''<!doctype html><html lang="en"><meta charset="utf-8">
    <meta name="viewport" content="width=device-width,initial-scale=1"><title>DirtyData Lab</title>
    <style>body{{font:16px system-ui;background:#101527;color:#ecf0ff;max-width:1000px;margin:40px auto;padding:24px}}
    h1{{font-size:44px;margin-bottom:8px}}.tag{{color:#69e3c0}}.stats{{display:flex;gap:16px;flex-wrap:wrap}}
    .card{{background:#1c2440;border-radius:14px;padding:20px;flex:1;min-width:150px}}
    b{{font-size:30px;display:block}}table{{border-collapse:collapse;width:100%;margin:20px 0}}
    th,td{{padding:12px;border-bottom:1px solid #35405b;text-align:left}}small{{color:#b6c2df}}
    a{{color:#69e3c0}}</style><header><span class="tag">SYNTHETIC DATA QUALITY CHALLENGE</span>
    <h1>DirtyData Lab</h1><p>Break data deliberately. Measure what your checks catch.</p></header>
    <div class="stats"><div class="card"><b>{truth['base_rows']}</b>clean rows</div>
    <div class="card"><b>{truth['dirty_rows']}</b>dirty rows</div><div class="card"><b>{truth['event_count']}</b>
    injected events</div><div class="card"><b>{truth['seed']}</b>reproducible seed</div></div>
    <h2>Injected errors</h2><table><tr><th>Error type</th><th>Events</th></tr>{rows}</table>
    <h2>Example answer-key events</h2><table><tr><th>Row ID</th><th>Column</th><th>Error</th><th>Operation</th></tr>{samples}</table>
    <small>This report reveals ground truth. Keep it out of detector inputs. Event rate is not a cell error rate.
    The rule baseline is a smoke test, not an independent benchmark of generalization.</small></html>'''
    Path(path).write_text(body, encoding='utf-8')


def detect(records, contract):
    """Reference baseline uses only dirty records and the public schema contract."""
    required = set(contract['required_columns'])
    p = contract['fields']
    seen = set()
    result = []
    def flag(row, column, kind):
        result.append({'row_id': row['row_id'], 'column': column, 'error_type': kind})
    for row in records:
        if not required <= set(row):
            raise ValueError('CSV is missing contract columns')
        if not row[p['name']]:
            flag(row, p['name'], 'missing_value')
        if row[p['id']] in seen:
            flag(row, p['id'], 'duplicate_id')
        seen.add(row[p['id']])
        try:
            date.fromisoformat(row[p['date']])
        except ValueError:
            flag(row, p['date'], 'invalid_date')
        try:
            amount = Decimal(row[p['amount']])
            if not amount.is_finite():
                raise ValueError('Non-finite amount is outside this baseline contract')
            if amount < Decimal(contract['amount_min']):
                flag(row, p['amount'], 'negative_amount')
        except InvalidOperation as exc:
            raise ValueError('Non-numeric amount is outside this baseline contract') from exc
        if row['category'] not in contract['categories']:
            flag(row, 'category', 'invalid_category')
        if row[p['name']] != row[p['name']].strip():
            flag(row, p['name'], 'extra_whitespace')
        value = row['postal_code']
        # This is a fictional five-digit code, not validation of any country's postal system.
        if value.isdigit() and len(value) == 4:
            flag(row, 'postal_code', 'leading_zero_loss')
        if row[p['fk']] not in contract['parent_ids']:
            flag(row, p['fk'], 'orphan_reference')
    return result


def evaluate(truth, predictions):
    """Exact localization: (row_id, column, error_type). Repeated predictions are deduplicated."""
    def key(item):
        if not isinstance(item, dict) or any(not isinstance(item.get(k), str) or not item[k]
                                              for k in ('row_id', 'column', 'error_type')):
            raise ValueError('Predictions need nonempty string row_id, column and error_type')
        if item['error_type'] not in ERRORS:
            raise ValueError(f"Unknown error_type: {item['error_type']}")
        return tuple(item[k] for k in ('row_id', 'column', 'error_type'))
    if not isinstance(predictions, list):
        raise ValueError('Predictions must be a JSON list')
    expected = {key(e) for e in truth['events']}
    actual = {key(e) for e in predictions}
    def metrics(a, b):
        tp, fp, fn = len(a & b), len(b - a), len(a - b)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        return {'true_positives': tp, 'false_positives': fp, 'false_negatives': fn,
                'precision': precision, 'recall': recall, 'f1': f1}
    return {**metrics(expected, actual), 'prediction_count': len(predictions),
            'unique_prediction_count': len(actual), 'ground_truth_events': len(expected),
            'by_error': {kind: metrics({x for x in expected if x[2] == kind},
                                      {x for x in actual if x[2] == kind}) for kind in ERRORS},
            'false_positive_keys': sorted(actual - expected),
            'false_negative_keys': sorted(expected - actual),
            'scoring_unit': '(row_id, column, error_type)',
            'zero_denominator_policy': 'precision/recall/F1 are 0 when their denominators are 0'}
