"""Ventas en la misma transacción SQLite que autoriza y actualiza el inventario."""

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine, text

from app.domain.catalog import Product, Record
from app.domain.identity import User
from app.infrastructure.catalog import CatalogTransaction, now
from app.infrastructure.identity import IdentityStore


class SalesTransaction(CatalogTransaction):
    def sale(self, sale_id: int) -> Record | None:
        return self.row("SELECT * FROM sales WHERE id=:id", id=sale_id)

    def sale_by_key(self, key: str) -> Record | None:
        return self.row("SELECT * FROM sales WHERE idempotency_key=:key", key=key)

    def sale_items(self, sale_id: int) -> list[Record]:
        return [dict(row) for row in self.connection.execute(
            text("SELECT * FROM sale_items WHERE sale_id=:id ORDER BY product_id"), {"id": sale_id}
        ).mappings()]

    def payment(self, sale_id: int) -> Record:
        row = self.row("SELECT method,amount_cents FROM payments WHERE sale_id=:id", id=sale_id)
        assert row is not None
        return row

    def add_sale(self, actor: User, key: str, request_hash: str, total: int) -> int:
        self.execute(
            """INSERT INTO sales(idempotency_key,request_hash,user_id,username_snapshot,total_cents,created_at_utc)
            VALUES(:key,:hash,:user,:username,:total,:now)""",
            key=key, hash=request_hash, user=actor.id, username=actor.username, total=total, now=now(),
        )
        return self.connection.exec_driver_sql("SELECT last_insert_rowid()").scalar_one()

    def add_item(self, sale_id: int, item: Record) -> None:
        self.execute(
            """INSERT INTO sale_items(sale_id,product_id,product_name_snapshot,product_code_snapshot,unit_price_cents,quantity,subtotal_cents)
            VALUES(:sale_id,:product_id,:product_name_snapshot,:product_code_snapshot,:unit_price_cents,:quantity,:subtotal_cents)""",
            sale_id=sale_id, **item,
        )

    def add_payment(self, sale_id: int, method: str, total: int) -> None:
        self.execute(
            "INSERT INTO payments(sale_id,method,amount_cents) VALUES(:id,:method,:total)",
            id=sale_id, method=method, total=total,
        )

    def sale_movement(self, actor: User, product: Product, delta: int, sale_id: int, reason: str, kind: str) -> None:
        self.execute(
            """INSERT INTO stock_movements(product_id,movement_type,quantity_delta,stock_before,stock_after,reference_type,reference_id,performed_by,reason,created_at_utc)
            VALUES(:product,:kind,:delta,:before,:after,'SALE',:sale,:actor,:reason,:now)""",
            product=product.id, kind=kind, delta=delta, before=product.stock_quantity,
            after=product.stock_quantity + delta, sale=sale_id, actor=actor.id, reason=reason, now=now(),
        )

    def void_sale(self, sale_id: int, actor: User, reason: str) -> None:
        self.execute(
            "UPDATE sales SET status='VOIDED',voided_at_utc=:now,voided_by=:actor,void_reason=:reason WHERE id=:id",
            id=sale_id, now=now(), actor=actor.id, reason=reason,
        )

    def sales(self, user_id: int | None, status: str | None, limit: int, offset: int) -> Record:
        params = {"user": user_id, "status": status, "limit": limit, "offset": offset}
        where = "WHERE (:user IS NULL OR s.user_id=:user) AND (:status IS NULL OR s.status=:status)"
        total = self.connection.execute(text("SELECT COUNT(*) FROM sales s " + where), params).scalar_one()
        rows = self.connection.execute(text(
            "SELECT s.id,s.user_id,s.username_snapshot,s.status,s.total_cents,s.created_at_utc,p.method AS payment_method "
            "FROM sales s JOIN payments p ON p.sale_id=s.id " + where + " ORDER BY s.id DESC LIMIT :limit OFFSET :offset"
        ), params).mappings()
        return {"items": [dict(row) for row in rows], "total": total}


class SalesStore:
    def __init__(self, engine: Engine):
        self.identity = IdentityStore(engine)

    @contextmanager
    def transaction(self, write: bool = False) -> Iterator[SalesTransaction]:
        with self.identity.transaction(write) as tx:
            yield SalesTransaction(tx.connection)
