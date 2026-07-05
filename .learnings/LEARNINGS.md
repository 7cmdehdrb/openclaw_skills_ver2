## [LRN-20260225-001] best_practice

**Logged**: 2026-02-25T22:13:00+09:00
**Priority**: medium
**Status**: pending
**Area**: config

### Summary
gmail-calendar-scheduler 일정 제목 생성 품질을 한 단계 더 개선할 필요가 있음

### Details
현재 스케줄러는 메일 제목 대신 업무성 문구를 뽑도록 개선됐지만, 일부 케이스에서 본문의 긴 문장/증빙 문구가 제목으로 선택되어 캘린더 가독성이 떨어진다. 사용자 피드백: 기능은 전반적으로 괜찮고, 제목 생성 품질만 소폭 개선하면 충분함.

### Suggested Action
- 제목 생성 규칙을 “짧은 액션형 문구 우선”으로 강화
- 불필요한 접두/접미(예: 안내문, 증빙 리스트) 제거 필터 추가
- 최대 길이 외에 금지 패턴(숫자 나열/문장부호 과다/증빙항목 시작문구) 적용

### Metadata
- Source: user_feedback
- Related Files: skills/gmail-calendar-scheduler/scripts/sync.py
- Tags: gmail, calendar, title-quality, parser
- Pattern-Key: scheduler.title_quality
- Recurrence-Count: 1
- First-Seen: 2026-02-25
- Last-Seen: 2026-02-25

---

## [LRN-20260306-001] correction

**Logged**: 2026-03-06T10:32:00Z
**Priority**: high
**Status**: pending
**Area**: docs

### Summary
PDF→Notion 스킬 실행 시 일부 케이스에서 중복 페이지와 불완전 페이지가 발생했다.

### Details
사용자 피드백: (1) 핵심 이미지 누락, (2) 원본 PDF가 로컬 경로 텍스트만 남고 Notion 실제 첨부가 누락, (3) 재실행/스케줄 겹침 시 동일 논문 2개 생성.

### Suggested Action
- source fingerprint 기반 idempotent upsert 강제
- per-fingerprint run lock 추가
- 이미지 인라인/원본 첨부 실업로드 확인 전 완료 보고 금지
- 체크리스트에 실패 재시도 및 완료 금지 규칙 명시

### Metadata
- Source: user_feedback
- Related Files: skills/chatgpt-pdf-to-notion-temporary/SKILL.md, skills/chatgpt-pdf-to-notion-temporary/references/checklist.md
- Tags: pdf-notion, idempotency, qa

---
