from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, date, timedelta
from typing import Protocol, Optional
from zoneinfo import ZoneInfo


#temporary
import random


class MarketCalendarSource(Protocol):
    def is_open_on_date(self, day: date, tz: str) -> bool: ...


@dataclass(frozen=True)
class PandasMarketCalendarsSource:
    calendar_code: str = "XNYS"  # NYSE par défaut

    def is_open_on_date(self, day: date, tz: str) -> bool:
        try:
            import pandas_market_calendars as mcal  # type: ignore
        except ModuleNotFoundError as e:
            raise RuntimeError(
                "Dépendance manquante: pandas_market_calendars."
            ) from e

        cal = mcal.get_calendar(self.calendar_code)
        start = day.strftime("%Y-%m-%d")
        end = start
        schedule = cal.schedule(start_date=start, end_date=end)
        return not schedule.empty


class USMarketsCalendar:

    def __init__(self):
        self._source: MarketCalendarSource = PandasMarketCalendarsSource()
        self.tz = "America/New_York"

    def is_open_today(self, now: Optional[datetime] = None) -> bool:
        now = now or datetime.now(tz=ZoneInfo("UTC"))

        if now.tzinfo is None:
            now = now.replace(tzinfo=ZoneInfo("UTC"))

        now_market = now.astimezone(ZoneInfo(self.tz))
        return self._source.is_open_on_date(now_market.date(), tz=self.tz)


    def is_open_tomorrow(self, now: Optional[datetime] = None) -> bool:
        now = now or datetime.now(tz=ZoneInfo("UTC"))

        if now.tzinfo is None:
            now = now.replace(tzinfo=ZoneInfo("UTC"))

        now_market = now.astimezone(ZoneInfo(self.tz))
        tomorrow_market = (now_market + timedelta(days=1)).date()
        return self._source.is_open_on_date(tomorrow_market, tz=self.tz)



class RandomMarketCalendar:

    def __init__(self, seed: Optional[int] = None, p_true: float = 5 / 7):
        self._rng = random.Random(seed)
        self._p_true = float(p_true)

    def is_open_today(self, now: Optional[datetime] = None) -> bool:
        _ = now or datetime.now(tz=ZoneInfo("UTC"))
        return self._rng.random() < self._p_true
