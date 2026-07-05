# Runbook

## Target DB
Use the validated data-bearing DB id when provided by user.

## Core update policy
- Round numeric updates to 2 decimals.
- Update only:
  - `현재가`
  - `환율 기록` (USD rows)

## Cash handling
If user requests cash exclusion:
- Skip rows where ticker is `KRW` or `USD` for `현재가` update.
- Always skip rows where ticker is `-` (cash-like placeholder) for `현재가` update.

## Typical failure reasons
- Ticker formatting mismatch (`BRK.b` vs `BRK-B`)
- Delisted/unavailable symbol from yfinance
- Missing Notion column or wrong column type