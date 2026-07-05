#!/usr/bin/env python3
import argparse
import base64
import json
import os
import re
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from pathlib import Path
from urllib import parse, request

API_GMAIL = "https://gateway.maton.ai/google-mail/gmail/v1/users/me"
API_CAL = "https://gateway.maton.ai/google-calendar/calendar/v3/calendars/primary/events"

DATE_PATTERNS = [
    re.compile(r"(20\d{2})[/-](\d{1,2})[/-](\d{1,2})"),
    re.compile(r"(\d{1,2})[/-](\d{1,2})"),
    re.compile(r"(\d{1,2})\s*월\s*(\d{1,2})\s*일"),
]
TIME_PATTERNS = [
    re.compile(r"\b(\d{1,2}):(\d{2})\b"),
    re.compile(r"(오전|오후)\s*(\d{1,2})\s*시(?:\s*(\d{1,2})\s*분)?"),
    re.compile(r"\b(\d{1,2})\s*시(?:\s*(\d{1,2})\s*분)?\b"),
]

ACTION_PATTERNS = [
    re.compile(r"(발표|제출|미팅|회의|면담|콜|인터뷰|점검|리뷰|보고|작성|수정|검토|요청|마감)"),
]


def read_key():
    k = os.getenv("MATON_API_KEY", "").strip()
    if k:
        return k
    p = Path.home() / ".config/maton/api_key"
    if p.exists():
        return p.read_text().strip()
    raise RuntimeError("MATON_API_KEY not found")


def api_json(url, key, method="GET", body=None):
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
    req = request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {key}")
    req.add_header("Content-Type", "application/json")
    with request.urlopen(req, timeout=30) as r:
        return json.load(r)


def decode_body(payload):
    if not payload:
        return ""
    body = payload.get("body", {})
    if body.get("data"):
        try:
            return base64.urlsafe_b64decode(body["data"] + "==").decode("utf-8", "ignore")
        except Exception:
            pass
    for part in payload.get("parts", []) or []:
        txt = decode_body(part)
        if txt:
            return txt
    return ""


def llm_schedule_judgment(subject, snippet, body):
    """LLM judgment first (OpenAI-compatible), fallback to heuristic if key missing/fails.
    Returns dict: {is_schedule: bool, confidence: float, reason: str}
    """
    text_raw = "\n".join([subject or "", snippet or "", body or ""])

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if api_key:
        try:
            payload = {
                "model": "gpt-4o-mini",
                "temperature": 0,
                "response_format": {"type": "json_object"},
                "messages": [
                    {
                        "role": "system",
                        "content": "Classify whether an email should create a calendar task/schedule. Return JSON with keys: is_schedule(boolean), confidence(0-1), reason(short). Treat reminder/request/deadline/action-needed mails as schedule-worthy even if exact date/time is missing."
                    },
                    {
                        "role": "user",
                        "content": f"Subject: {subject}\nSnippet: {snippet}\nBody: {body}"
                    }
                ]
            }
            req = request.Request(
                "https://api.openai.com/v1/chat/completions",
                data=json.dumps(payload).encode("utf-8"),
                method="POST",
            )
            req.add_header("Authorization", f"Bearer {api_key}")
            req.add_header("Content-Type", "application/json")
            with request.urlopen(req, timeout=25) as r:
                resp = json.load(r)
            content = resp["choices"][0]["message"]["content"]
            o = json.loads(content)
            return {
                "is_schedule": bool(o.get("is_schedule", False)),
                "confidence": float(o.get("confidence", 0.5)),
                "reason": str(o.get("reason", "llm_classification"))[:200],
            }
        except Exception:
            pass

    # Fallback heuristic
    text = text_raw.lower()
    strong_task_terms = [
        "요청", "리마인드", "마감", "제출", "작성", "검토", "회의", "미팅", "면담", "인터뷰", "콜", "일정",
        "due", "deadline", "meeting", "appointment", "submit", "follow up", "reminder", "action required"
    ]
    weak_noise_terms = ["newsletter", "subscribe", "promotion", "advertisement", "digest", "광고", "뉴스레터", "구독"]

    score = 0
    for t in strong_task_terms:
        if t in text:
            score += 1
    for t in weak_noise_terms:
        if t in text:
            score -= 1

    is_schedule = score >= 1
    confidence = min(0.95, max(0.05, 0.5 + (score * 0.12)))
    reason = "heuristic_task_or_schedule_intent" if is_schedule else "heuristic_no_actionable_schedule_intent"
    return {"is_schedule": is_schedule, "confidence": round(confidence, 4), "reason": reason}


def clean_email_text(subject, snippet, body):
    raw = "\n".join([subject or "", snippet or "", body or ""])
    lines = []
    for ln in raw.splitlines():
        s = ln.strip()
        if not s:
            continue
        low = s.lower()
        # Remove quoted/reply header lines and email metadata noise
        if low.startswith('on ') and 'wrote:' in low:
            continue
        if re.search(r"\d{4}년\s*\d{1,2}월\s*\d{1,2}일.*님이\s*작성", s):
            continue
        if low.startswith('from:') or low.startswith('sent:') or low.startswith('to:') or low.startswith('subject:'):
            continue
        if s.startswith('>'):
            continue
        lines.append(s)
    return "\n".join(lines)


def hard_exclude_informational(subject, text, from_addr=''):
    low = ((subject or '') + '\n' + (text or '') + '\n' + (from_addr or '')).lower()
    patterns = [
        '취소 완료', '처리 완료', '안내드립니다', '참고 바랍니다', '회신 드립니다', '답변드립니다',
        '계정', '인증', 'verify your email', 'verify your account', 'confirm your email',
        'newsletter', 'newsletters', 'issue covers', 'explore sensors', 'springer nature',
        'author experience', '광고', '프로모션', '구독', 'unsubscribe',
        '수강 신청 문의의 건', '문의의 건'
    ]
    sender_patterns = ['no-reply', 'noreply', 'newsletter', 'springer', 'mdpi', 'sensors', 'google']
    if any(p in low for p in patterns):
        return True
    if any(p in (from_addr or '').lower() for p in sender_patterns):
        return True
    return False


def needs_action(text):
    low = (text or '').lower()
    positive = ['요청', '필요', '검토 부탁', '회신 부탁', '제출', '작성', '마감', '확인 요청', '사양 확인', '리뷰 부탁']
    negative = ['안내드립니다', '참고 바랍니다', '처리 완료', '취소 완료', '답변 드립니다', '회신드립니다', '완료했습니다']
    return any(p in low for p in positive) and not any(n in low for n in negative)


def has_explicit_date_or_time(text):
    if not text:
        return False
    # Require schedule context near date/time to avoid accidental header/quoted times.
    schedule_context = ['회의', '미팅', '면담', '콜', '인터뷰', '마감', '까지', '전까지', '제출', '발표', '일정', '예약', 'due', 'deadline', 'meeting']
    low = text.lower()

    has_date = any(p.search(text) for p in DATE_PATTERNS)
    has_time = any(p.search(text) for p in TIME_PATTERNS)
    has_ctx = any(k in low for k in schedule_context)

    return (has_date or has_time) and has_ctx


def parse_datetime(text, now_local):
    date_obj = None
    date_match = None
    for p in DATE_PATTERNS:
        m = p.search(text)
        if not m:
            continue
        g = m.groups()
        if len(g) == 3 and len(g[0]) == 4:
            y, mo, d = map(int, g)
        else:
            y = now_local.year
            mo, d = map(int, g[-2:])
        try:
            date_obj = datetime(y, mo, d)
            date_match = m
            break
        except ValueError:
            continue

    if not date_obj:
        return None, None, True

    hour = minute = None

    # Prefer explicit Korean time expressions first: 오전/오후, N시
    for p in TIME_PATTERNS[1:]:
        m = p.search(text)
        if not m:
            continue
        g = m.groups()
        if len(g) >= 2 and g[0] in ("오전", "오후"):
            ap, h = g[0], int(g[1])
            mm = int(g[2] or 0)
            if ap == "오후" and h < 12:
                h += 12
            if ap == "오전" and h == 12:
                h = 0
            hour, minute = h, mm
            break
        elif len(g) >= 2 and g[1] is not None:
            hour, minute = int(g[0]), int(g[1])
            break

    # HH:MM is accepted only when near the detected date context (avoid email header/noise time)
    if hour is None:
        for m in TIME_PATTERNS[0].finditer(text):
            hh, mm = int(m.group(1)), int(m.group(2))
            if hh > 23 or mm > 59:
                continue
            if date_match is not None:
                dist = abs(m.start() - date_match.end())
                if dist > 40:
                    continue
            hour, minute = hh, mm
            break

    if hour is None:
        return date_obj.date().isoformat(), None, True

    start = datetime(date_obj.year, date_obj.month, date_obj.day, hour, minute)
    end = start + timedelta(hours=1)
    return start.isoformat(), end.isoformat(), False


def derive_event_title(subject, text):
    t = (text or '')
    s = (subject or '')

    # Intent-first concise title mapping
    if '사양' in t and ('검토' in t or '리뷰' in t or '확인' in t):
        return '최종 사양서 리뷰'
    if '입찰' in t and '사양' in t:
        return '입찰 사양 검토'
    if '최종보고서' in t and ('작성' in t or '제출' in t):
        return '최종보고서 작성'
    if '최종발표' in t and ('작성' in t or '준비' in t):
        return '최종발표 자료 준비'
    if '요청자료' in t and ('전달' in t or '제출' in t):
        return '요청자료 전달'
    if '재요청' in t:
        return '재요청 건 확인'

    # Generic extraction from actionable line
    lines = [l.strip() for l in t.splitlines() if l.strip()]
    for l in lines[:20]:
        if any(k in l for k in ['요청','검토','작성','제출','마감','회의','미팅','면담','리뷰','확인']):
            cleaned = re.sub(r"\[[^\]]+\]", "", l)
            cleaned = re.sub(r"^(re:|fwd:|fw:)\s*", "", cleaned, flags=re.IGNORECASE)
            cleaned = re.sub(r"(안내드립니다|참고 바랍니다|처리 완료|취소 완료|회신 드립니다|답변드립니다)", "", cleaned)
            cleaned = re.sub(r"\s+", " ", cleaned).strip(" -:,")
            if 4 <= len(cleaned) <= 30:
                return cleaned

    base = re.sub(r"^(re:|fwd:|fw:)\s*", "", s, flags=re.IGNORECASE)
    base = re.sub(r"\[[^\]]+\]\s*", "", base)
    base = re.sub(r"\s+", " ", base).strip()
    return (base[:24] + ' 업무') if base else '업무 일정'

def load_state(path):
    if not path.exists():
        return {
            "thread_latest_processed": {},
            "created_event_by_message": {},
            "last_run_at": None,
        }
    return json.loads(path.read_text())


def save_state(path, state):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2))


def append_jsonl(path, row):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max", type=int, default=15)
    ap.add_argument("--tz", default="Asia/Seoul")
    ap.add_argument("--days", type=int, default=None, help="Gmail lookback window in days (e.g., 90)")
    ap.add_argument("--ignore-state", action="store_true", help="Ignore existing processed state for this run")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    key = read_key()
    workspace = Path(__file__).resolve().parents[3]
    state_path = workspace / "memory/gmail-calendar-sync-state.json"
    log_path = workspace / "memory/gmail-calendar-processed.jsonl"
    state = {
        "thread_latest_processed": {},
        "created_event_by_message": {},
        "last_run_at": None,
    } if args.ignore_state else load_state(state_path)

    now_local = datetime.now()
    gmail_query = "in:inbox"
    if args.days is not None:
        after_date = (datetime.now() - timedelta(days=args.days)).strftime("%Y/%m/%d")
        gmail_query = f"in:inbox after:{after_date}"
    q = parse.urlencode({"maxResults": args.max, "q": gmail_query, "includeSpamTrash": "false"})
    ids = api_json(f"{API_GMAIL}/messages?{q}", key).get("messages", [])

    created = skipped = errors = 0
    created_details = []

    for m in ids:
        mid = m["id"]
        try:
            msg = api_json(f"{API_GMAIL}/messages/{mid}?format=full", key)
            thread_id = msg.get("threadId")
            internal_ms = int(msg.get("internalDate", "0"))

            if state["created_event_by_message"].get(mid):
                skipped += 1
                continue

            prev_thread_ms = int(state["thread_latest_processed"].get(thread_id, 0))
            if internal_ms <= prev_thread_ms:
                skipped += 1
                continue

            headers = {h.get("name", ""): h.get("value", "") for h in msg.get("payload", {}).get("headers", [])}
            subject = headers.get("Subject", "")
            from_addr = headers.get("From", "")
            snippet = msg.get("snippet", "")
            body = decode_body(msg.get("payload", {}))
            text = clean_email_text(subject, snippet, body)

            # hard exclude obvious informational/marketing mails
            if hard_exclude_informational(subject, text, from_addr):
                state["thread_latest_processed"][thread_id] = internal_ms
                skipped += 1
                append_jsonl(log_path, {
                    "processed_at": datetime.now(timezone.utc).isoformat(),
                    "message_id": mid,
                    "thread_id": thread_id,
                    "subject": subject,
                    "action": "skip",
                    "reason": "hard_exclude_informational",
                })
                continue

            # Must be actionable, not just conversational/info mail
            if not needs_action(text):
                state["thread_latest_processed"][thread_id] = internal_ms
                skipped += 1
                append_jsonl(log_path, {
                    "processed_at": datetime.now(timezone.utc).isoformat(),
                    "message_id": mid,
                    "thread_id": thread_id,
                    "subject": subject,
                    "action": "skip",
                    "reason": "not_actionable",
                })
                continue

            # LLM-style semantic judgment for schedule/task intent
            llm_judge = llm_schedule_judgment(subject, snippet, text)
            if not llm_judge["is_schedule"]:
                state["thread_latest_processed"][thread_id] = internal_ms
                skipped += 1
                append_jsonl(log_path, {
                    "processed_at": datetime.now(timezone.utc).isoformat(),
                    "message_id": mid,
                    "thread_id": thread_id,
                    "subject": subject,
                    "action": "skip",
                    "reason": "llm_not_schedule",
                    "llm_confidence": llm_judge["confidence"],
                    "llm_reason": llm_judge["reason"],
                })
                continue

            explicit_dt = has_explicit_date_or_time(text)
            start, end, all_day = parse_datetime(text, now_local) if explicit_dt else (None, None, True)
            if not start:
                # ASAP rule: schedule intent but no reliable explicit date/time
                received_local = datetime.fromtimestamp(internal_ms / 1000, tz=timezone.utc).astimezone(ZoneInfo(args.tz))
                day0 = received_local.date().isoformat()
                day2 = (received_local.date() + timedelta(days=2)).isoformat()  # end is exclusive
                start, end, all_day = day0, day2, True

            event_title = derive_event_title(subject, text)
            event = {
                "summary": event_title[:120],
                "description": f"Gmail 자동생성\n\n원본 메일 제목: {subject}\nThread: {thread_id}\nMessage: {mid}\n\nSnippet:\n{snippet}",
            }
            if all_day:
                d = start
                # For parsed date without time, end may be None -> one-day all-day.
                # For ASAP fallback, end is precomputed as +2 days (exclusive end).
                end_day = end if end else (datetime.fromisoformat(d) + timedelta(days=1)).date().isoformat()
                event["start"] = {"date": d}
                event["end"] = {"date": end_day}
            else:
                event["start"] = {"dateTime": start, "timeZone": args.tz}
                event["end"] = {"dateTime": end, "timeZone": args.tz}

            event_id = None
            if not args.dry_run:
                created_event = api_json(API_CAL, key, method="POST", body=event)
                event_id = created_event.get("id")
                state["created_event_by_message"][mid] = event_id

            state["thread_latest_processed"][thread_id] = internal_ms
            created += 1
            created_details.append({
                "subject": subject,
                "event_summary": event["summary"],
                "event_id": event_id,
                "all_day": all_day,
                "start": event["start"],
                "end": event["end"],
            })
            append_jsonl(log_path, {
                "processed_at": datetime.now(timezone.utc).isoformat(),
                "message_id": mid,
                "thread_id": thread_id,
                "subject": subject,
                "action": "create_event" if not args.dry_run else "dry_run_create",
                "event_id": event_id,
                "all_day": all_day,
                "start": event["start"],
                "end": event["end"],
            })

        except Exception as e:
            errors += 1
            append_jsonl(log_path, {
                "processed_at": datetime.now(timezone.utc).isoformat(),
                "message_id": m.get("id"),
                "action": "error",
                "error": str(e),
            })

    state["last_run_at"] = datetime.now(timezone.utc).isoformat()
    save_state(state_path, state)

    print(json.dumps({
        "scanned": len(ids),
        "created": created,
        "created_details": created_details,
        "skipped": skipped,
        "errors": errors,
        "state": str(state_path),
        "log": str(log_path),
        "dry_run": args.dry_run,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
