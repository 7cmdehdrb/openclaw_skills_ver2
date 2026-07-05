#!/usr/bin/env python3
import argparse
import json
import subprocess
import sys
from datetime import date, datetime, timezone
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parent
STATUS_FILE = SKILL_DIR / "daily_status.json"
LOG_DIR = SKILL_DIR / "logs"
LEGACY_CRON_LOG = SKILL_DIR / "cron.log"
LABS = (44, 49)


def iso_now():
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def is_weekend_mode():
    today = date.today()
    try:
        import holidays

        kr_holidays = holidays.country_holidays("KR", years=[today.year])
        return today in kr_holidays or today.weekday() == 5
    except Exception:
        return today.weekday() == 5


def run_lab(lab_no, weekend):
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    started = datetime.now(timezone.utc).astimezone()
    stamp = started.strftime("%Y%m%d_%H%M%S")
    log_path = LOG_DIR / f"daily_lab{lab_no}_{stamp}.log"
    cmd = [sys.executable, "app.py", "--lab", str(lab_no)]
    if weekend:
        cmd.insert(2, "--weekend")

    print(f"[{started.strftime('%Y-%m-%d %H:%M:%S')}] start lab {lab_no}")
    with log_path.open("w", encoding="utf-8") as log:
        proc = subprocess.Popen(
            cmd,
            cwd=SKILL_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        assert proc.stdout is not None
        for line in proc.stdout:
            print(line, end="")
            log.write(line)
        exit_code = proc.wait()

    finished = datetime.now(timezone.utc).astimezone()
    status = "success" if exit_code == 0 else "failure"
    print(
        f"[{finished.strftime('%Y-%m-%d %H:%M:%S')}] done lab {lab_no}: {status} ({exit_code})"
    )
    return {
        "lab": lab_no,
        "status": status,
        "exit_code": exit_code,
        "started_at": started.isoformat(timespec="seconds"),
        "finished_at": finished.isoformat(timespec="seconds"),
        "duration_seconds": round((finished - started).total_seconds(), 2),
        "log": str(log_path),
    }


def write_status(status):
    STATUS_FILE.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")


def notify_failure(status):
    failed = [r for r in status["results"] if r["status"] != "success"]
    lines = [
        "[알림] 일일 연구실 안전점검 자동 실행 실패",
        f"- 실행 시각: {status['started_at']}",
        f"- 모드: {'weekend' if status['weekend_mode'] else 'normal'}",
    ]
    for row in failed:
        lines.append(
            f"- lab {row['lab']}: 실패(exit {row['exit_code']}), 로그: {row['log']}"
        )
    lines.append(f"- 상태 파일: {STATUS_FILE}")
    message = "\n".join(lines)
    try:
        subprocess.run(
            ["openclaw", "system", "event", "--mode", "now", "--text", message],
            check=True,
            cwd=SKILL_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=30,
        )
        return {"sent": True, "error": None}
    except Exception as exc:
        return {"sent": False, "error": str(exc)}


def print_status():
    if not STATUS_FILE.exists():
        if LEGACY_CRON_LOG.exists():
            lines = LEGACY_CRON_LOG.read_text(encoding="utf-8", errors="ignore").splitlines()
            start_indexes = [
                i for i, line in enumerate(lines) if "start daily run" in line
            ]
            if start_indexes:
                block = lines[start_indexes[-1] :]
                ok_count = sum(
                    "모든 작업이 성공적으로 완료되었습니다" in line for line in block
                )
                failed = any("에러 발생:" in line for line in block)
                done = any("done daily run" in line for line in block)
                status = "success" if done and ok_count >= len(LABS) and not failed else "unknown"
                print(
                    json.dumps(
                        {
                            "status": status,
                            "source": str(LEGACY_CRON_LOG),
                            "reason": "daily_status.json not found; inferred from latest legacy cron block",
                            "latest_block_start": block[0] if block else None,
                            "success_markers": ok_count,
                            "done_marker": done,
                            "failure_marker": failed,
                        },
                        ensure_ascii=False,
                        indent=2,
                    )
                )
                return 0 if status == "success" else 1
        print(
            json.dumps(
                {"status": "unknown", "reason": "status file and legacy cron log not found"},
                ensure_ascii=False,
                indent=2,
            )
        )
        return 1
    print(STATUS_FILE.read_text(encoding="utf-8"))
    return 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--status", action="store_true", help="최근 실행 상태 JSON 출력")
    args = parser.parse_args()
    if args.status:
        return print_status()

    started = iso_now()
    weekend = is_weekend_mode()
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] start daily run")
    print(f"[*] mode: {'weekend' if weekend else 'normal'}")

    results = [run_lab(lab, weekend) for lab in LABS]
    overall = "success" if all(r["status"] == "success" for r in results) else "failure"
    status = {
        "status": overall,
        "started_at": started,
        "finished_at": iso_now(),
        "weekend_mode": weekend,
        "results": results,
        "alert": {"sent": False, "error": None},
    }
    write_status(status)

    if overall != "success":
        status["alert"] = notify_failure(status)
        write_status(status)

    print(json.dumps(status, ensure_ascii=False, indent=2))
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] done daily run: {overall}")
    return 0 if overall == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
