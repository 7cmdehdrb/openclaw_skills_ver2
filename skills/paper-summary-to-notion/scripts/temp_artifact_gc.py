#!/usr/bin/env python3
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

REGISTRY = Path('/home/soyu/.openclaw/workspace/memory/temp-artifacts.json')


def parse_iso(ts: str):
    try:
        return datetime.fromisoformat(ts.replace('Z', '+00:00'))
    except Exception:
        return None


def delete_path(p: Path):
    if not p.exists():
        return 'missing'
    if p.is_dir():
        shutil.rmtree(p, ignore_errors=True)
    else:
        p.unlink(missing_ok=True)
    return 'deleted'


def main():
    if not REGISTRY.exists():
        print(json.dumps({'ok': True, 'deleted': 0, 'pending': 0, 'registry': str(REGISTRY)}))
        return

    data = json.loads(REGISTRY.read_text())
    items = data.get('items', [])
    now = datetime.now(timezone.utc)

    deleted = 0
    pending = 0
    for it in items:
        if it.get('status') == 'deleted':
            continue
        exp = parse_iso(it.get('expiresAt', ''))
        if exp is None:
            it['status'] = 'invalid_expiry'
            continue
        if now >= exp:
            status = delete_path(Path(it['path']))
            it['status'] = status
            it['deletedAt'] = now.isoformat()
            if status in ('deleted', 'missing'):
                deleted += 1
        else:
            pending += 1

    data['items'] = items
    REGISTRY.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    print(json.dumps({'ok': True, 'deleted': deleted, 'pending': pending, 'registry': str(REGISTRY)}))


if __name__ == '__main__':
    main()
