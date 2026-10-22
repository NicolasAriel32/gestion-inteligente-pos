"""Agregados exactos y lectura WAL explícita; nunca SUM de dinero en SQLite."""

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine, text
from sqlalchemy.exc import OperationalError

from app.domain.catalog import Record
from app.domain.identity import IdentityError
from app.domain.reporting import Interval
from app.infrastructure.identity import IdentityTransaction

WHERE = "s.status='COMPLETED' AND s.created_at_utc>=:start AND s.created_at_utc<:end"


class ReportingTransaction(IdentityTransaction):
    @staticmethod
    def params(interval: Interval) -> dict[str, str]:
        data = interval.wire()
        return {"start": data["start_utc"], "end": data["end_utc"]}

    def metrics(self, interval: Interval) -> dict[str, int]:
        params = self.params(interval)
        header = self.connection.execute(text(
            f"SELECT COUNT(*) AS sales, pos_sum(s.total_cents) AS revenue_cents FROM sales s WHERE {WHERE}"
        ), params).mappings().one()
        units = self.connection.execute(text(
            f"SELECT pos_sum(i.quantity) FROM sales s JOIN sale_items i ON i.sale_id=s.id WHERE {WHERE}"
        ), params).scalar_one()
        return {"sales": header["sales"], "revenue_cents": int(header["revenue_cents"] or "0"), "units": int(units or "0")}

    def rankings(self, interval: Interval, order: str) -> list[Record]:
        # Fixed whitelist; compare decimal text numerically by length then lexicographically.
        assert order in {"units", "revenue_cents"}
        rows = self.connection.execute(text(f"""
            WITH ranked AS (
                SELECT i.product_id, pos_sum(i.quantity) AS units,
                       pos_sum(i.subtotal_cents) AS revenue_cents
                FROM sales s JOIN sale_items i ON i.sale_id=s.id WHERE {WHERE}
                GROUP BY i.product_id
            ) SELECT r.*,
                (SELECT i.product_name_snapshot FROM sale_items i JOIN sales s ON s.id=i.sale_id
                 WHERE {WHERE} AND i.product_id=r.product_id
                 ORDER BY s.created_at_utc DESC,s.id DESC LIMIT 1) AS name,
                (SELECT i.product_code_snapshot FROM sale_items i JOIN sales s ON s.id=i.sale_id
                 WHERE {WHERE} AND i.product_id=r.product_id
                 ORDER BY s.created_at_utc DESC,s.id DESC LIMIT 1) AS code
            FROM ranked r ORDER BY length(r.{order}) DESC,r.{order} DESC,r.product_id LIMIT 10
        """), self.params(interval)).mappings()
        return [dict(row) for row in rows]

    def hours(self, interval: Interval) -> list[Record]:
        rows = self.connection.execute(text(f"""
            SELECT pos_hour(s.created_at_utc) AS hour,COUNT(*) AS sales,
                   pos_sum(s.total_cents) AS revenue_cents FROM sales s
            WHERE {WHERE} GROUP BY hour ORDER BY hour
        """), self.params(interval)).mappings()
        by_hour = {row["hour"]: row for row in rows}
        return [{"hour": hour, "sales": str(by_hour[hour]["sales"]),
                 "revenue_cents": by_hour[hour]["revenue_cents"]} if hour in by_hour else
                {"hour": hour, "sales": "0", "revenue_cents": "0"} for hour in range(24)]


class ReportingStore:
    def __init__(self, engine: Engine):
        self.engine = engine

    @contextmanager
    def transaction(self) -> Iterator[ReportingTransaction]:
        try:
            with self.engine.connect() as connection:
                connection.exec_driver_sql("BEGIN")
                try:
                    yield ReportingTransaction(connection)
                finally:
                    connection.rollback()
        except OperationalError as exc:
            raise IdentityError(503, "Base local no disponible; reintentá el reporte") from exc
