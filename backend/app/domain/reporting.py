"""Calendario comercial y redondeo exacto, sin dependencias de persistencia."""

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

from app.domain.identity import IdentityError

Period = Literal["today", "yesterday", "7d", "30d", "custom"]
ZONE = ZoneInfo("America/Argentina/Buenos_Aires")


@dataclass(frozen=True)
class Interval:
    start: datetime
    end: datetime

    def wire(self) -> dict[str, str]:
        return {"start_utc": self.start.astimezone(UTC).isoformat(),
                "end_utc": self.end.astimezone(UTC).isoformat(),
                "start_local": self.start.isoformat(), "end_local": self.end.isoformat()}


def periods(period: Period, now: datetime, start: date | None, end: date | None) -> tuple[Interval, Interval]:
    local = now.astimezone(ZONE)
    today = local.date()
    if period == "custom":
        if start is None or end is None:
            raise IdentityError(422, "Indicá ambas fechas")
    else:
        if start is not None or end is not None:
            raise IdentityError(422, "Las fechas solo se usan en rango personalizado")
        end = today - timedelta(days=1) if period == "yesterday" else today
        start = end - timedelta(days={"7d": 6, "30d": 29}.get(period, 0))
    assert start is not None and end is not None
    days = (end - start).days + 1
    if not (1 <= days <= 366 and 2000 <= start.year <= end.year <= 2099 and end <= today):
        raise IdentityError(422, "Elegí un rango de 1 a 366 días entre 2000 y 2099, sin fechas futuras")
    first = datetime.combine(start, time(), ZONE)
    last = local if end == today else datetime.combine(end + timedelta(days=1), time(), ZONE)
    shift = timedelta(days=days)
    return Interval(first, last), Interval(first - shift, last - shift)


def rounded(numerator: int, denominator: int) -> int:
    assert denominator > 0
    sign = -1 if numerator < 0 else 1
    return sign * ((abs(numerator) * 2 + denominator) // (denominator * 2))


def comparison(n: int, d: int, old_n: int, old_d: int) -> dict[str, str | None]:
    delta = n * old_d - old_n * d
    base = old_n * d
    return {"delta": str(rounded(delta, d * old_d)),
            "percent_bp": str(rounded(delta * 10000, base)) if base else ("0" if not delta else None)}
