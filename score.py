#!/usr/bin/env python3
"""Development-only practice scorer; this file is not imported by main.py."""
import json
import math
import os
import pathlib
import statistics
import subprocess
import sys
import tempfile
import time

ROOT = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else pathlib.Path(__file__).resolve().parent)
KIT = pathlib.Path('/home/hatch/workspace/makefun/polymarket-nvidia-ceo-forecast-01-kit/input')
Z = (-1.644854, -0.67449, 0.0, 0.67449, 1.644854)
TAUS = (0.05, 0.25, 0.5, 0.75, 0.95)

def load(case_id):
    return json.loads((KIT / (case_id + '.in')).read_text())

def loss_row(actual, row):
    return [max(t * (actual - q), (t - 1) * (actual - q)) * 100 for t, q in zip(TAUS, row)]

def main():
    case_losses, base_losses = [], []
    all_errors, covered, total = [], 0, 0
    failed = False
    for i in range(5):
        cid = f'p0{i}'
        case, nxt = load(cid), load(f'p0{i+1}')
        next_by_id = {m['id']: m for m in nxt['markets']}
        with tempfile.TemporaryDirectory() as inp, tempfile.TemporaryDirectory() as out:
            pathlib.Path(inp, cid + '.in').write_text(json.dumps(case, separators=(',', ':')))
            env = os.environ.copy()
            env['MAKEFUN_INPUT_DIR'], env['MAKEFUN_OUTPUT_DIR'] = inp, out
            start = time.perf_counter()
            try:
                run = subprocess.run([sys.executable, str(ROOT / 'main.py')], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=8)
                runtime = time.perf_counter() - start
            except subprocess.TimeoutExpired:
                runtime = time.perf_counter() - start
                run = None
            valid = run is not None and run.returncode == 0 and runtime < 8
            output_path = pathlib.Path(out, cid + '.out')
            forecasts = None
            if valid and output_path.is_file() and output_path.stat().st_size <= 1048576:
                try:
                    data = json.loads(output_path.read_text())
                    valid = type(data) is dict and list(data) == ['forecasts'] and type(data['forecasts']) is list
                    forecasts = data['forecasts'] if valid else None
                except Exception:
                    valid = False
            expected = [m['id'] for m in case['markets']]
            by_id = {}
            if valid and forecasts is not None:
                valid = len(forecasts) == len(expected)
                for f in forecasts:
                    if type(f) is not dict or set(f) != {'id', 'q'} or f.get('id') in by_id:
                        valid = False
                        break
                    by_id[f['id']] = f.get('q')
                valid = valid and set(by_id) == set(expected)
            if valid:
                for mid, rows in by_id.items():
                    if type(rows) is not list or len(rows) != 240:
                        valid = False; break
                    for row in rows:
                        if type(row) is not list or len(row) != 5 or any(type(q) not in (int, float) or not math.isfinite(q) or q < 0 or q > 1 for q in row) or any(row[j] > row[j+1] for j in range(4)):
                            valid = False; break
                    if not valid: break
        if not valid:
            print(f'{cid}: INVALID runtime={runtime:.4f}s')
            failed = True
            continue
        entry_items, baseline_items = [], []
        for m in case['markets']:
            actual_market = next_by_id.get(m['id'])
            if actual_market is None:
                continue
            # Current case's final sample and the next 240 grid minutes align by index.
            start_index = len(m['prices'])
            ys = actual_market['prices'][start_index:start_index + 240]
            if len(ys) < 240:
                continue
            rows = by_id[m['id']]
            x = m['prices'][-1]
            for h, (y, row) in enumerate(zip(ys, rows), 1):
                entry_items.extend(loss_row(y, row))
                base = [min(1.0, max(0.0, x + z * 0.0025 * math.sqrt(h))) for z in Z]
                baseline_items.extend(loss_row(y, base))
                all_errors.append(abs(y - row[2]) * 100)
                covered += row[0] <= y <= row[4]
                total += 1
        if not entry_items:
            print(f'{cid}: INVALID no scored items')
            failed = True
            continue
        el, bl = statistics.mean(entry_items), statistics.mean(baseline_items)
        case_losses.append(el); base_losses.append(bl)
        print(f'{cid}: entry={el:.6f} baseline={bl:.6f} runtime={runtime:.4f}s')
    if len(case_losses) == 5:
        print(f'mean (5 cases): entry={statistics.mean(case_losses):.6f} baseline={statistics.mean(base_losses):.6f}')
        print(f'median error={statistics.mean(all_errors):.6f} coverage90={covered / total:.6f}')
    return 1 if failed or len(case_losses) != 5 else 0

if __name__ == '__main__':
    raise SystemExit(main())
