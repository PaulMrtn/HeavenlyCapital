#!/usr/bin/env python3

import subprocess
import logging
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
import pytz


NYC = pytz.timezone("America/New_York")
MAIN = Path(__file__).parent / "main.py"
LOG_FILE = Path(__file__).parent / "launcher.log"

START_HOUR = 4
RETRY_DELAY = 60
SLEEP_INTERVAL = 30

CIRCUIT_BREAKER_WINDOW = 300
CIRCUIT_BREAKER_MAX = 3


EXIT_CODES = {
    0:  "OK",
    10: "STRATEGIC_SETUP_COMPLETED",
    20: "MARKET_SETUP_COMPLETED",
    30: "MARKET_CLOSED_TODAY",
    40: "ERROR",
    50: "BROKER_UNAVAILABLE"
}


class NycFormatter(logging.Formatter):
    def formatTime(self, record, datefmt=None):
        return datetime.fromtimestamp(record.created, NYC).strftime("%Y-%m-%d %H:%M:%S")

formatter = NycFormatter("%(asctime)s [NYC] %(levelname)s — %(message)s")

log = logging.getLogger("launcher")
log.setLevel(logging.INFO)

for handler in [logging.FileHandler(LOG_FILE), logging.StreamHandler(sys.stdout)]:
    handler.setFormatter(formatter)
    log.addHandler(handler)


def now_nyc() -> datetime:
    return datetime.now(NYC)


def next_start_nyc() -> datetime:
    """Calcule le prochain 04h00 NYC — aujourd'hui si pas encore passé, sinon demain."""
    now = now_nyc()
    target = now.replace(hour=START_HOUR, minute=0, second=0, microsecond=0)
    if now >= target:
        target += timedelta(days=1)
    return target


def wait_until(target: datetime) -> None:
    log.info(f"Next start scheduled at {target.strftime('%Y-%m-%d %H:%M:%S')} NYC")
    while now_nyc() < target:
        remaining = (target - now_nyc()).total_seconds()
        hours = int(remaining // 3600)
        minutes = int((remaining % 3600) // 60)
        log.info(f"Sleeping — {hours}h {minutes}m remaining")
        time.sleep(min(600, int(remaining)))


def run_main() -> int:
    """Lance main.py et retourne l'exit code."""
    log.info(f"Starting {MAIN.name}")
    result = subprocess.run([sys.executable, str(MAIN)])
    code = result.returncode
    label = EXIT_CODES.get(code, "UNEXPECTED_CRASH")
    log.info(f"Exit code: {code} — {label}")
    return code


# ── Circuit Breaker ───────────────────────────────────────────────────────────

class CircuitBreaker:
    def __init__(self, max_crashes: int = CIRCUIT_BREAKER_MAX, window: float = CIRCUIT_BREAKER_WINDOW):
        self._max = max_crashes
        self._window = window
        self._crashes: list[float] = []

    def record(self) -> None:
        now = time.time()
        self._crashes.append(now)
        self._crashes = [t for t in self._crashes if now - t < self._window]

    @property
    def is_open(self) -> bool:
        return len(self._crashes) >= self._max

    def reset(self) -> None:
        self._crashes.clear()


# ── Main Loop ─────────────────────────────────────────────────────────────────

def main() -> None:
    log.info("=" * 60)
    log.info("  HeavenlyCapital Launcher started")
    log.info(f"  {now_nyc().strftime('%Y-%m-%d %H:%M:%S')} NYC")
    log.info("=" * 60)

    breaker = CircuitBreaker()

    while True:
        code = run_main()

        # ── Exit codes nominaux ────────────────────────────────────────────────

        if code == 10:  # STRATEGIC_SETUP_COMPLETED
            log.info("Strategic setup completed — restarting immediately")
            breaker.reset()
            continue

        if code == 20:  # MARKET_SETUP_COMPLETED
            log.info("Market session completed — waiting for next start")
            breaker.reset()
            wait_until(next_start_nyc())
            continue

        if code == 30:  # MARKET_CLOSED_TODAY
            log.info("Market closed today — waiting for next start")
            breaker.reset()
            wait_until(next_start_nyc())
            continue

        if code == 40:  # ERROR
            log.error("Fatal error — stopping launcher")
            log.error("Manual intervention required")
            break

        if code == 50:  # BROKER_UNAVAILABLE
            log.warning("Broker unavailable — retrying in 10s")
            breaker.record()
            if breaker.is_open:
                log.error("Circuit breaker open — manual intervention required")
                break
            time.sleep(10)
            continue


        # ── Unexpected Crash ────────────────────────────────────────────────────

        log.warning(f"Unexpected exit code: {code} — recording crash")
        breaker.record()

        if breaker.is_open:
            log.error(f"Circuit breaker open — {CIRCUIT_BREAKER_MAX} crashes in {CIRCUIT_BREAKER_WINDOW}s")
            log.error("Manual intervention required")
            break

        log.info(f"Retrying in {RETRY_DELAY}s")
        time.sleep(RETRY_DELAY)


if __name__ == "__main__":
    main()