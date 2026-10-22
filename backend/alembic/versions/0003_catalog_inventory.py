"""Catálogo, movimientos y auditoría general; actualización aditiva de F2."""

from alembic import op

revision = "0003_catalog_inventory"
down_revision = "0002_identity"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for statement in (
        """CREATE TABLE audit_events (
            id INTEGER PRIMARY KEY, actor_id INTEGER NOT NULL REFERENCES users(id),
            action TEXT NOT NULL, entity_type TEXT NOT NULL, entity_id INTEGER NOT NULL,
            event_data TEXT NOT NULL DEFAULT '{}', created_at_utc TEXT NOT NULL)""",
        """INSERT INTO audit_events(id,actor_id,action,entity_type,entity_id,event_data,created_at_utc)
            SELECT id,actor_id,action,entity_type,entity_id,event_data,created_at_utc FROM audit_log""",
        "CREATE INDEX audit_events_entity ON audit_events(entity_type,entity_id)",
        """CREATE TABLE categories (
            id INTEGER PRIMARY KEY, name TEXT NOT NULL CHECK(length(trim(name)) BETWEEN 1 AND 100),
            name_key TEXT NOT NULL UNIQUE, is_active INTEGER NOT NULL DEFAULT 1
            CHECK(is_active IN (0,1)))""",
        """CREATE TABLE products (
            id INTEGER PRIMARY KEY, code TEXT UNIQUE CHECK(code IS NULL OR length(code) BETWEEN 1 AND 64),
            name TEXT NOT NULL CHECK(length(trim(name)) BETWEEN 1 AND 160),
            category_id INTEGER REFERENCES categories(id),
            price_cents INTEGER NOT NULL CHECK(typeof(price_cents)='integer' AND price_cents BETWEEN 0 AND 9007199254740991),
            cost_cents INTEGER CHECK(cost_cents IS NULL OR (typeof(cost_cents)='integer' AND cost_cents BETWEEN 0 AND 9007199254740991)),
            stock_quantity INTEGER NOT NULL DEFAULT 0 CHECK(typeof(stock_quantity)='integer' AND stock_quantity BETWEEN 0 AND 9007199254740991),
            minimum_stock INTEGER NOT NULL DEFAULT 0 CHECK(typeof(minimum_stock)='integer' AND minimum_stock BETWEEN 0 AND 9007199254740991),
            is_active INTEGER NOT NULL DEFAULT 1 CHECK(is_active IN (0,1)),
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL)""",
        "CREATE INDEX products_category ON products(category_id)",
        """CREATE TABLE stock_movements (
            id INTEGER PRIMARY KEY, product_id INTEGER NOT NULL REFERENCES products(id),
            movement_type TEXT NOT NULL CHECK(movement_type IN ('INITIAL','IN','ADJUSTMENT','SALE','VOID')),
            quantity_delta INTEGER NOT NULL CHECK(typeof(quantity_delta)='integer' AND quantity_delta != 0 AND quantity_delta BETWEEN -9007199254740991 AND 9007199254740991),
            stock_before INTEGER NOT NULL CHECK(typeof(stock_before)='integer' AND stock_before BETWEEN 0 AND 9007199254740991),
            stock_after INTEGER NOT NULL CHECK(typeof(stock_after)='integer' AND stock_after BETWEEN 0 AND 9007199254740991),
            reference_type TEXT NOT NULL, reference_id INTEGER NOT NULL,
            performed_by INTEGER NOT NULL REFERENCES users(id),
            reason TEXT NOT NULL CHECK(length(trim(reason)) BETWEEN 3 AND 240),
            request_key TEXT UNIQUE, created_at_utc TEXT NOT NULL,
            CHECK(stock_after=stock_before+quantity_delta))""",
        "CREATE INDEX stock_movements_product ON stock_movements(product_id,id)",
    ):
        op.execute(statement)


def downgrade() -> None:
    raise RuntimeError("F3 no admite downgrade destructivo de catálogo, movimientos y auditoría")
