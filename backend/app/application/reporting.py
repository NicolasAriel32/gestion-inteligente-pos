"""Reporte completo autorizado y leído en una única instantánea."""

from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import UTC, date, datetime
from typing import Protocol

from app.application.identity import digest
from app.domain.catalog import Record
from app.domain.identity import IdentityError, User
from app.domain.reporting import Interval, Period, comparison, periods, rounded


class ReportingUnit(Protocol):
    def session_user(self, token_hash: str, now: int) -> User: ...
    def metrics(self, interval: Interval) -> dict[str, int]: ...
    def rankings(self, interval: Interval, order: str) -> list[Record]: ...
    def hours(self, interval: Interval) -> list[Record]: ...


class ReportingPersistence(Protocol):
    def transaction(self) -> AbstractContextManager[ReportingUnit]: ...


class ReportingService:
    def __init__(self, store: ReportingPersistence, clock: Callable[[], float]):
        self.store, self.clock = store, clock

    def summary(self, token: str, period: Period, start: date | None, end: date | None) -> Record:
        timestamp = self.clock()
        with self.store.transaction() as tx:
            actor = tx.session_user(digest(token), int(timestamp))
            if actor.role != "ADMIN":
                raise IdentityError(403, "Se requiere rol ADMIN")
            current, previous = periods(period, datetime.fromtimestamp(timestamp, UTC), start, end)
            metrics, old = tx.metrics(current), tx.metrics(previous)
            changes = {key: comparison(metrics[key], 1, old[key], 1) for key in metrics}
            changes["average_cents"] = comparison(metrics["revenue_cents"], metrics["sales"] or 1,
                                                  old["revenue_cents"], old["sales"] or 1)
            hours = tx.hours(current)
            peak = max(int(h["sales"]) for h in hours)
            def wire(values: dict[str, int]) -> dict[str, str]:
                return {**{key: str(value) for key, value in values.items()},
                        "average_cents": str(rounded(values["revenue_cents"], values["sales"] or 1))}
            return {"period": current.wire(), "previous_period": previous.wire(),
                    "timezone": "America/Argentina/Buenos_Aires", "current": wire(metrics),
                    "previous": wire(old), "comparison": changes,
                    "top_units": tx.rankings(current, "units"),
                    "top_revenue": tx.rankings(current, "revenue_cents"), "hours": hours,
                    "peak_hours": [h["hour"] for h in hours if peak and int(h["sales"]) == peak]}
