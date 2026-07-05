#!/usr/bin/env python3
import json
import subprocess
from pathlib import Path
from datetime import datetime

WORKSPACE = Path('/home/soyu/.openclaw/workspace')
STATE = WORKSPACE / 'memory' / 'pdf-scheduler-state.json'
INBOUND = Path('/home/soyu/.openclaw/media/inbound')

# 이미 사용자 확인/완료된 파일(현 시점 기준)
DONE = {
    'f9bad4ed-3f26-4e92-818c-7c38616f97ff.pdf',
    'ace27e0e-2ea2-4c0b-a7bf-bf53cdb69f78.pdf',
    'c524a934-a9a3-4ceb-a3e0-42fe2b53983f.pdf',
}


def load_state():
    if STATE.exists():
        return json.loads(STATE.read_text())
    return {"processed": [], "lastRun": None}


def save_state(state):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2))


def main():
    state = load_state()
    processed = set(state.get('processed', []))

    pdfs = sorted([p for p in INBOUND.glob('*.pdf') if p.name not in DONE])
    targets = [p for p in pdfs if p.name not in processed]

    if not targets:
        state['lastRun'] = datetime.now().isoformat()
        state['status'] = 'idle_no_targets'
        save_state(state)
        return

    target = targets[0]
    text = (
        "[AUTO PDF JOB] 아래 PDF 1개를 스킬(chatgpt-pdf-to-notion-temporary, local-first)로 처리하세요. "
        "품질 기준(c90295e) 반드시 준수: 근거 기반 문제/방법/결과, 추정 수치 금지, 원본 PDF 첨부. "
        f"대상 파일: {target}"
    )

    # 시스템 이벤트로 메인 에이전트 깨우기
    subprocess.run([
        'openclaw', 'system', 'event',
        '--mode', 'now',
        '--text', text
    ], check=False)

    processed.add(target.name)
    state['processed'] = sorted(processed)
    state['lastRun'] = datetime.now().isoformat()
    state['lastTarget'] = target.name
    state['status'] = 'queued'
    save_state(state)


if __name__ == '__main__':
    main()
