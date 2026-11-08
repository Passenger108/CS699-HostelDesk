import threading
import time
from datetime import datetime

from flask import Flask

from app.cleaning.arrival import time_out_arrivals
from app.cleaning.delays import escalate_delays, expire_requests, miss_windows
from app.cleaning.service import time_out_offers
from app.common.models import utcnow
from app.common.time import week_start
from app.credits.service import grant_weekly_credits
from app.extensions import db
from app.workers.service import remind_stale_locations

TICK_SECONDS = 15
_state = {"week": None, "thread": None}
_lock = threading.Lock()


def run_due(now: datetime | None = None) -> dict:
    now = now or utcnow()
    result = {
        "offers_timed_out": time_out_offers(now),
        "arrivals_closed": time_out_arrivals(now),
        "delays_escalated": escalate_delays(now),
        "windows_missed": miss_windows(now),
        "requests_expired": expire_requests(now),
        "locations_reminded": remind_stale_locations(now),
        "weekly_credits": None,
    }
    if _state["week"] != week_start(now):
        result["weekly_credits"] = grant_weekly_credits(now)
        db.session.commit()
        _state["week"] = week_start(now)
    return result


def _loop(app: Flask) -> None:
    while True:
        with app.app_context():
            try:
                run_due()
            except Exception:
                db.session.rollback()
                app.logger.exception("Timer run failed")
        time.sleep(TICK_SECONDS)


def start_timers(app: Flask) -> None:
    with _lock:
        if app.config["TIMERS_ENABLED"] and _state["thread"] is None:
            _state["thread"] = threading.Thread(target=_loop, args=(app,), daemon=True)
            _state["thread"].start()
