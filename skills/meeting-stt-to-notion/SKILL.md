---
name: meeting-stt-to-notion
description: Turn meeting STT transcript text files into structured meeting notes and actionable todo lists, then publish to Notion. Use when the user provides a .txt transcript from speech-to-text and asks for detailed organization, decisions/risks capture, and task extraction with owner/deadline/priority in a Notion page.
---

# meeting-stt-to-notion

Process STT transcript text into clean, practical meeting documentation and publish it to Notion under the allowed parent page.

## Workflow

1. Validate inputs
2. Parse and structure meeting content
3. Extract actionable tasks
4. Draft a final page body
5. Publish to Notion
6. Report back with page URL + brief summary

## 1) Validate inputs

- Require a transcript `.txt` file path.
- Read the file and estimate transcript quality.
- If transcript is extremely noisy (broken lines, repeated fragments), clean minimally before summarizing.
- Confirm Notion credentials are available (`~/.config/notion/api_key` or `NOTION_API_KEY`).
- Restrict page creation to user-approved parent page (e.g., `나의 개인 페이지` subtree).

## 2) Parse and structure meeting content

Build these sections from transcript evidence:

- Meeting summary (3-6 bullets)
- Main discussion topics (grouped by theme)
- Decisions made (explicitly agreed points)
- Open questions / unresolved issues
- Risks / blockers

Rules:
- Preserve concrete facts and numbers.
- Mark uncertainty as `추정` instead of inventing certainty.
- If speakers are unknown, use neutral labels (`참석자 A/B`).

## 3) Extract actionable tasks

For each task, capture:

- Task title
- Owner (or `미지정`)
- Due date/time (or `미정`)
- Priority (`높음/중간/낮음`, default `중간`)
- Context note (1 line)

If deadlines are relative (e.g., "다음 주까지"), convert to explicit date only when date context is clear; otherwise keep original phrasing and mark `해석 필요`.

## 4) Draft final Notion page body

Use the fixed structure in `references/notion-meeting-template.md`.

Mandatory format order:

1. 회의 개요
2. 주요 논의 내용 (의제 단위)
3. 결정 사항
4. 지시 사항 / 액션 아이템

Rules:
- Do not add `한 줄 요약` section.
- Do not include time-range details (e.g., 22:49~1:05:30).
- Do not add `메타` section.
- Do not use low-value helper labels (e.g., `(의제별 상세)`).
- Move all unresolved/open-check items into `지시 사항 / 액션 아이템`.
- Keep evidence-based wording; avoid speculative claims.
- 중요: 마크다운 기호를 텍스트로 남기지 말 것 (`-`, `|`, `##` 등).
- 중첩 항목은 반드시 실제 Notion 자식 불릿(children)으로 생성.
- 액션 아이템은 마크다운 테이블(`|`) 금지. (Notion 불릿/자식불릿으로 구조화)

## 5) Publish to Notion

Recommended API flow:

1. Search parent page by title (`나의 개인 페이지`) or use provided `page_id`
2. Create child page with title pattern:
   - `[회의정리] YYYY-MM-DD - <주제>`
3. Append structured blocks for each section

Minimum metadata to include in title/body:

- Meeting date (if detectable)
- Transcript source filename
- Generation timestamp

## 6) Report to user

Always return:

- Created page title
- Notion URL
- Extracted task count
- Any ambiguity that needs user confirmation

## Quality bar

- Do not hallucinate decisions or owners.
- Keep Korean output natural and business-readable.
- Prefer completeness over brevity for task extraction.
- If transcript lacks key context, add a `정보 부족` note instead of guessing.