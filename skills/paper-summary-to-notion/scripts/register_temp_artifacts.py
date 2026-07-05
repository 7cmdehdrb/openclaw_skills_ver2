#!/usr/bin/env python3
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

REGISTRY = Path('/home/soyu/.openclaw/workspace/memory/temp-artifacts.json')


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def main():
    ap = argparse.ArgumentParser(description='Register temporary artifacts for delayed cleanup')
    ap.add_argument('paths', nargs='+', help='File/dir paths to register')
    ap.add_argument('--ttl-hours', type=float, default=6.0, help='Delete-after hours (default: 6)')
    args = ap.parse_args()

    REGISTRY.parent.mkdir(parents=True, exist_ok=True)
    data = {'items': []}
    if REGISTRY.exists():
        try:
            data = json.loads(REGISTRY.read_text())
        except Exception:
            data = {'items': []}

    items = data.get('items', [])
    existing = {(it.get('path'), it.get('expiresAt')) for it in items}

    added = 0
    for p in args.paths:
        rp = str(Path(p).resolve())
        expires = datetime.now(timezone.utc).timestamp() + args.ttl_hours * 3600
        exp_iso = datetime.fromtimestamp(expires, tz=timezone.utc).isoformat()
        rec = {
            'path': rp,
            'addedAt': now_iso(),
            'expiresAt': exp_iso,
            'ttlHours': args.ttl_hours,
            'status': 'pending',
        }
        key = (rec['path'], rec['expiresAt'])
        if key in existing:
            continue
        items.append(rec)
        added += 1

    data['items'] = items
    REGISTRY.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    print(json.dumps({'ok': True, 'added': added, 'registry': str(REGISTRY)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
