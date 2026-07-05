---
name: notion-portfolio-price-refresh
description: Refresh stock portfolio market fields in Notion. Use when user asks to update a Notion stock portfolio DB by fetching USD/KRW first, then iterating rows to update current price and exchange-rate fields.
---

# notion-portfolio-price-refresh

Update Notion portfolio rows with latest market values in a fixed sequence.

## Fixed sequence

1. Fetch USD/KRW rate
2. Iterate portfolio rows and update price/rate fields

## Preconditions

- Notion API key exists (`~/.config/notion/api_key` or `NOTION_API_KEY`).
- Target DB is the data-bearing `주식 포트폴리오` DB (user-approved ID preferred).
- Required columns exist:
  - `티커` (rich_text)
  - `종목명` (title or rich_text)  ← 변동 알림 표시에 사용
  - `현재가` (number)
  - `통화` (select)
  - `환율 기록` (number)

## Step 1) Fetch exchange rate

- Use yfinance ticker `KRW=X`.
- Resolve in this order:
  1. `fast_info.last_price`
  2. `history(period="1d", interval="1m")` last close (fallback)
- Round to 2 decimals.
- If both fail, stop and report failure.

## Step 2) Update portfolio rows

- Query rows from the target DB.
- For each row:
  - Read `티커`, `통화`.
  - Resolve market ticker:
    - If ticker has `.` suffix, keep as-is.
    - If ticker looks like Korean code (leading digit), use `.KS` suffix.
    - Keep US symbols as-is (e.g., `TSM`, `AAPL`, `BRK-B`).
    - Normalize known exception: `BRK.b` → `BRK-B`.
  - Fetch latest price via yfinance (same fallback order as above for price).
  - Update `현재가` with 2-decimal rounding.
  - If `통화 == USD`, update `환율 기록` with Step 1 rate.
  - If `통화` is cash (`KRW`, `USD`) and user asked to exclude cash, skip price updates.
  - If `티커 == "-"`, always skip price updates (cash-like/non-market asset placeholder).

## Retry and failure policy (required)

- If refresh fails, retry up to **3 times** (max attempts = 3).
- Use lightweight backoff between retries (e.g., 5s → 15s → 30s).
- A failure includes: exchange-rate fetch failure, DB query/update failure, or fatal auth/object errors.
- If any retry succeeds, report success summary normally.
- If all 3 attempts fail, send a **final failure alert** including:
  - failure stage (rate fetch / DB query / page update)
  - last error message
  - attempt count (3/3)
  - recommended fix (e.g., re-share Notion DB to integration)

## Output to user

Return a short execution summary (always, including scheduled auto-runs):

- Applied USD/KRW rate
- Retry status (attempt n/3)
- Final alert when failed after 3/3

Conditional reporting rules:

- Report `Updated row count` and `Skipped row count/reasons` **only when there is an anomaly or actionable issue**.
  - Do not mention normal cash skips (`KRW`, `USD`) by default.
  - Mention counts/reasons when ticker unresolved, price fetch failure, unexpected skip, or update failure exists.
- Report `3%+ move alerts` **only when at least one symbol meets threshold**.
  - Format: `- <종목명> 종목이 <N%> 상승/하락 했습니다. (이전 <A> → 현재 <B>)`
  - 변동종목 표시는 반드시 `종목명` 기준으로 한다. (티커/종목코드 표기 금지)
  - `종목명`이 비어 있으면 `티커`를 임시 대체값으로 사용하고, 이를 요약에 1회 경고한다.
  - Compute change from each row's `현재가` before update to new fetched `현재가`.
  - If none meet threshold, omit this section entirely.

Additionally report portfolio value delta in KRW after update:

- Compute `총 평가금액 변동(원화)` as:
  - `KRW 자산 변동합` + `(적용 환율) × (USD 자산 변동합)`
- Where each asset delta is `(업데이트 후 가격 - 업데이트 전 가격) × 보유량`.
- Round to nearest KRW and present sign (+/-) clearly.
- Include a one-line alert, e.g.:
  - `- 포트폴리오 평가금액이 +123,456원 변동했습니다. (적용 환율: 1,433.18)`

## Safety / behavior

- Never modify DBs outside user-approved scope.
- Do not create/delete rows unless explicitly requested.
- Prefer minimal, deterministic updates to existing fields only.
