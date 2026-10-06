import argparse
import json
from pathlib import Path
from .core import generate, detect, evaluate, read_csv, dump_json, ERRORS, PROFILES


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def main():
    parser = argparse.ArgumentParser(description='DirtyData Lab — reproducible data-quality challenges')
    sub = parser.add_subparsers(dest='command', required=True)
    gen = sub.add_parser('generate', help='Generate a clean dataset, dirty dataset and hidden answer key')
    gen.add_argument('--rows', type=int, default=100)
    gen.add_argument('--seed', type=int, default=42)
    gen.add_argument('--rate', type=float, default=.2, help='Injected event budget = floor(rows * rate)')
    gen.add_argument('--profile', choices=PROFILES, default='customers')
    gen.add_argument('--errors', nargs='+', choices=ERRORS)
    gen.add_argument('--output', default='output')
    det = sub.add_parser('detect', help='Run a transparent schema-rule baseline; no answer key input')
    det.add_argument('--input', required=True)
    det.add_argument('--contract', required=True)
    det.add_argument('--output', default='predictions.json')
    ev = sub.add_parser('evaluate', help='Score exact event-level detections')
    ev.add_argument('--truth', required=True)
    ev.add_argument('--predictions', required=True)
    ev.add_argument('--output', default='evaluation.json')
    args = parser.parse_args()
    try:
        if args.command == 'generate':
            result = generate(args.output, args.rows, args.seed, args.rate, args.profile, args.errors)
            print(f"Generated {result['base_rows']} clean rows, {result['dirty_rows']} dirty rows, "
                  f"{result['event_count']} injected events. Seed: {result['seed']}.")
            print(f'Open {args.output}/report.html for the visual answer-key report.')
        elif args.command == 'detect':
            predictions = detect(read_csv(args.input), load(args.contract))
            Path(args.output).parent.mkdir(parents=True, exist_ok=True)
            dump_json(args.output, predictions)
            print(f'Wrote {len(predictions)} baseline detections to {args.output}.')
        else:
            result = evaluate(load(args.truth), load(args.predictions))
            Path(args.output).parent.mkdir(parents=True, exist_ok=True)
            dump_json(args.output, result)
            print(f"Precision: {result['precision']:.3f} | Recall: {result['recall']:.3f} | F1: {result['f1']:.3f}")
    except (ValueError, KeyError, OSError) as exc:
        parser.exit(2, f'Error: {exc}\n')

if __name__ == '__main__':
    main()
