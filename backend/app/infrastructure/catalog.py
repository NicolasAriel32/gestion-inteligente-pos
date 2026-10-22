"""Persistencia de catálogo en la misma unidad transaccional que autoriza la sesión."""

import json
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime

from sqlalchemy import Engine, text

from app.domain.catalog import Category, Product, Record
from app.domain.identity import User
from app.infrastructure.identity import IdentityStore, IdentityTransaction


def now() -> str:
    return datetime.now(UTC).isoformat()


class CatalogTransaction(IdentityTransaction):
    def event(self, actor: User, action: str, entity: str, target: int, data: Record) -> None:
        self.execute(
            """INSERT INTO audit_events(actor_id,action,entity_type,entity_id,event_data,created_at_utc)
            VALUES(:actor,:action,:entity,:target,:data,:now)""",
            actor=actor.id,
            action=action,
            entity=entity,
            target=target,
            data=json.dumps(data, ensure_ascii=False),
            now=now(),
        )

    def category(self, category_id: int) -> Category | None:
        row = self.row("SELECT id,name,is_active FROM categories WHERE id=:id", id=category_id)
        return Category(row["id"], row["name"], bool(row["is_active"])) if row else None

    def categories(self, active_only: bool) -> list[Category]:
        rows = self.connection.execute(
            text(
                "SELECT id,name,is_active FROM categories WHERE (:active=0 OR is_active=1) ORDER BY name_key,id"
            ),
            {"active": int(active_only)},
        ).mappings()
        return [Category(r["id"], r["name"], bool(r["is_active"])) for r in rows]

    def category_name_exists(self, name: str, excluding: int = 0) -> bool:
        return (
            self.row(
                "SELECT id FROM categories WHERE name_key=:key AND id!=:id",
                key=name.casefold(),
                id=excluding,
            )
            is not None
        )

    def save_category(
        self, name: str, category_id: int | None = None, active: bool = True
    ) -> Category:
        if category_id is None:
            self.execute(
                "INSERT INTO categories(name,name_key) VALUES(:name,:key)",
                name=name,
                key=name.casefold(),
            )
            category_id = self.connection.exec_driver_sql("SELECT last_insert_rowid()").scalar_one()
        else:
            self.execute(
                "UPDATE categories SET name=:name,name_key=:key,is_active=:active WHERE id=:id",
                name=name,
                key=name.casefold(),
                active=int(active),
                id=category_id,
            )
        category = self.category(category_id)
        assert category is not None
        return category

    def product(self, product_id: int) -> Product | None:
        row = self.row("SELECT * FROM products WHERE id=:id", id=product_id)
        if row is None:
            return None
        row["is_active"] = bool(row["is_active"])
        return Product(**row)

    def code_exists(self, code: str | None, excluding: int = 0) -> bool:
        return (
            bool(code)
            and self.row(
                "SELECT id FROM products WHERE code=:code AND id!=:id", code=code, id=excluding
            )
            is not None
        )

    def products(
        self,
        search: str,
        category_id: int | None,
        active_only: bool,
        low_stock: bool,
        limit: int,
        offset: int,
    ) -> Record:
        params = {
            "search": search.casefold(),
            "category": category_id,
            "active": int(active_only),
            "low": int(low_stock),
            "limit": limit,
            "offset": offset,
        }
        # SQLite lower() no cubre todo Unicode; casefold registrado por conexión abajo.
        where = """WHERE (:search='' OR instr(casefold(name),:search)>0 OR instr(casefold(coalesce(code,'')),:search)>0)
            AND (:category IS NULL OR category_id=:category)
            AND (:active=0 OR is_active=1) AND (:low=0 OR stock_quantity<=minimum_stock)"""
        total = self.connection.execute(
            text("SELECT count(*) FROM products " + where), params
        ).scalar_one()
        ids = self.connection.execute(
            text(
                "SELECT id FROM products " + where + " ORDER BY name,id LIMIT :limit OFFSET :offset"
            ),
            params,
        ).scalars()
        return {"items": [self.product(i) for i in ids], "total": total}

    def save_product(self, data: Record, product_id: int | None = None) -> Product:
        data = {**data, "updated_at": now()}
        if product_id is None:
            data.update(created_at=data["updated_at"], is_active=1)
            self.execute(
                """INSERT INTO products(name,code,category_id,price_cents,cost_cents,stock_quantity,minimum_stock,is_active,created_at,updated_at)
                VALUES(:name,:code,:category_id,:price_cents,:cost_cents,:stock_quantity,:minimum_stock,:is_active,:created_at,:updated_at)""",
                **data,
            )
            product_id = self.connection.exec_driver_sql("SELECT last_insert_rowid()").scalar_one()
        else:
            # Solo claves de un DTO validado y lista interna; nunca identificadores del cliente.
            allowed = {
                "name",
                "code",
                "category_id",
                "price_cents",
                "cost_cents",
                "minimum_stock",
                "is_active",
                "updated_at",
            }
            assert data.keys() <= allowed
            current = self.product(product_id)
            assert current is not None
            values = {key: getattr(current, key) for key in allowed - {"updated_at"}}
            values.update(data)
            self.execute(
                """UPDATE products SET name=:name,code=:code,category_id=:category_id,
                price_cents=:price_cents,cost_cents=:cost_cents,minimum_stock=:minimum_stock,
                is_active=:is_active,updated_at=:updated_at WHERE id=:id""",
                **values,
                id=product_id,
            )
        product = self.product(product_id)
        assert product is not None
        return product

    def change_stock(self, product_id: int, stock: int) -> None:
        self.execute(
            "UPDATE products SET stock_quantity=:stock,updated_at=:now WHERE id=:id",
            stock=stock,
            now=now(),
            id=product_id,
        )

    def movement(self, key: str) -> Record | None:
        return self.row("SELECT * FROM stock_movements WHERE request_key=:key", key=key)

    def add_movement(
        self,
        actor: User,
        product: Product,
        delta: int,
        reason: str,
        kind: str,
        key: str | None = None,
    ) -> Record:
        self.execute(
            """INSERT INTO stock_movements(product_id,movement_type,quantity_delta,stock_before,stock_after,reference_type,reference_id,performed_by,reason,request_key,created_at_utc)
            VALUES(:id,:kind,:delta,:before,:after,'PRODUCT',:id,:actor,:reason,:key,:now)""",
            id=product.id,
            kind=kind,
            delta=delta,
            before=product.stock_quantity,
            after=product.stock_quantity + delta,
            actor=actor.id,
            reason=reason,
            key=key,
            now=now(),
        )
        row = self.row("SELECT * FROM stock_movements WHERE id=last_insert_rowid()")
        assert row is not None
        return row

    def movements(self, product_id: int | None, limit: int, offset: int) -> Record:
        params = {"product": product_id, "limit": limit, "offset": offset}
        where = " WHERE (:product IS NULL OR product_id=:product)"
        rows = self.connection.execute(
            text(
                "SELECT * FROM stock_movements"
                + where
                + " ORDER BY id DESC LIMIT :limit OFFSET :offset"
            ),
            params,
        ).mappings()
        total = self.connection.execute(
            text("SELECT count(*) FROM stock_movements" + where), params
        ).scalar_one()
        return {"items": [dict(row) for row in rows], "total": total}


class CatalogStore:
    def __init__(self, engine: Engine):
        self.identity = IdentityStore(engine)

    @contextmanager
    def transaction(self, write: bool = False) -> Iterator[CatalogTransaction]:
        with self.identity.transaction(write) as tx:
            yield CatalogTransaction(tx.connection)
