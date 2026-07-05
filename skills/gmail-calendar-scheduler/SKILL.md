---
name: gmail-calendar-scheduler
description: Parse recent Gmail messages and create Google Calendar events for actionable tasks/appointments. Use when users ask to auto-scan Gmail and add schedules to Google Calendar, with dedup so already-processed emails/threads are skipped. Reads latest 15 messages and avoids confusing thread replies with truly new mail by tracking thread latest timestamp.
---

# gmail-calendar-scheduler

Scan Gmail (latest 15), detect date/time intents, and create Calendar events.

## What this skill does

1. Read latest 15 Gmail messages from inbox
2. Detect schedule/task intent from subject/snippet/body using LLM-style semantic judgment
3. Create Calendar event on detected date/time
   - If time is missing, create all-day event
   - If date/time is missing but ML says schedule, create ASAP all-day window: mail received day ~ +1 day (2-day window)
   - Event title should be task/appointment intent (not raw email subject)
4. Record processed state/log so previously handled emails are skipped
5. Avoid reply-vs-new confusion by tracking per-thread latest message timestamp

## State & logs

- State file: `memory/gmail-calendar-sync-state.json`
- Process log: `memory/gmail-calendar-processed.jsonl`

State structure:

```json
{
  "thread_latest_processed": {
    "<threadId>": 1738300000000
  },
  "created_event_by_message": {
    "<messageId>": "<eventId>"
  },
  "last_run_at": "2026-02-25T12:00:00Z"
}
```

## Run

```bash
python3 skills/gmail-calendar-scheduler/scripts/sync.py --max 15 --tz Asia/Seoul
```

Optional dry run:

```bash
python3 skills/gmail-calendar-scheduler/scripts/sync.py --max 15 --tz Asia/Seoul --dry-run
```

## Parsing rules

- Date candidates:
  - `YYYY-MM-DD`, `YYYY/MM/DD`, `M/D`, `M월 D일`
- Time candidates:
  - `HH:MM`, `H시`, `오전 H시`, `오후 H시`, `오전/오후 H시 M분`
- Intent keywords (Korean/English):
  - `회의`, `미팅`, `약속`, `일정`, `면담`, `콜`, `call`, `meeting`, `appointment`, `deadline`

If no intent keyword or no date is found, skip.

If date found and time missing, create all-day event.

## Safety

- Do not delete/modify Gmail messages.
- Do not overwrite existing events made by humans.
- For duplicates, skip based on state (message/thread).
- Use `MATON_API_KEY` from env or `~/.config/maton/api_key`.

## Typical output summary

- scanned messages
- newly created events
- created details: `메일 제목 -> 생성 일정(start/end, all-day, event_id)`
- skipped (already processed / no parseable date / no intent)
- errors
