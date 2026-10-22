"""Ventas y pagos locales: migración aditiva, historia conservada."""

from alembic import op

revision = "0004_checkout_history"
down_revision = "0003_catalog_inventory"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for statement in (
        """CREATE TABLE sales (
            id INTEGER PRIMARY KEY, idempotency_key TEXT NOT NULL UNIQUE CHECK(length(idempotency_key)=36),
            request_hash TEXT NOT NULL CHECK(length(request_hash)=64),
            user_id INTEGER NOT NULL REFERENCES users(id), username_snapshot TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'COMPLETED' CHECK(status IN ('COMPLETED','VOIDED')),
            total_cents INTEGER NOT NULL CHECK(typeof(total_cents)='integer' AND total_cents BETWEEN 0 AND 9007199254740991),
            created_at_utc TEXT NOT NULL, voided_at_utc TEXT, voided_by INTEGER REFERENCES users(id), void_reason TEXT,
            CHECK((status='COMPLETED' AND voided_at_utc IS NULL AND voided_by IS NULL AND void_reason IS NULL)
                OR (status='VOIDED' AND voided_at_utc IS NOT NULL AND voided_by IS NOT NULL AND void_reason IS NOT NULL AND length(trim(void_reason)) BETWEEN 3 AND 240)))""",
        "CREATE INDEX sales_user_date ON sales(user_id,created_at_utc,id)",
        """CREATE TABLE sale_items (
            id INTEGER PRIMARY KEY, sale_id INTEGER NOT NULL REFERENCES sales(id),
            product_id INTEGER NOT NULL REFERENCES products(id), product_name_snapshot TEXT NOT NULL,
            product_code_snapshot TEXT,
            unit_price_cents INTEGER NOT NULL CHECK(typeof(unit_price_cents)='integer' AND unit_price_cents BETWEEN 0 AND 9007199254740991),
            quantity INTEGER NOT NULL CHECK(typeof(quantity)='integer' AND quantity BETWEEN 1 AND 9007199254740991),
            subtotal_cents INTEGER NOT NULL CHECK(typeof(subtotal_cents)='integer' AND subtotal_cents BETWEEN 0 AND 9007199254740991),
            UNIQUE(sale_id,product_id), CHECK(subtotal_cents=unit_price_cents*quantity))""",
        """CREATE TABLE payments (
            id INTEGER PRIMARY KEY, sale_id INTEGER NOT NULL UNIQUE REFERENCES sales(id),
            method TEXT NOT NULL CHECK(method IN ('CASH','TRANSFER','DEBIT','CREDIT')),
            amount_cents INTEGER NOT NULL CHECK(typeof(amount_cents)='integer' AND amount_cents BETWEEN 0 AND 9007199254740991))""",
        """CREATE TRIGGER payment_matches_sale BEFORE INSERT ON payments BEGIN
            SELECT CASE WHEN NOT EXISTS(SELECT 1 FROM sale_items WHERE sale_id=NEW.sale_id)
                OR NEW.amount_cents != (SELECT total_cents FROM sales WHERE id=NEW.sale_id)
                OR NEW.amount_cents != (SELECT SUM(subtotal_cents) FROM sale_items WHERE sale_id=NEW.sale_id)
                THEN RAISE(ABORT,'payment does not match sale') END; END""",
        """CREATE TRIGGER sale_items_sealed BEFORE INSERT ON sale_items
            WHEN EXISTS(SELECT 1 FROM payments WHERE sale_id=NEW.sale_id)
            BEGIN SELECT RAISE(ABORT,'sale items are sealed'); END""",
        """CREATE TRIGGER sales_immutable BEFORE UPDATE ON sales
            WHEN NEW.id != OLD.id OR NEW.idempotency_key != OLD.idempotency_key
                OR NEW.request_hash != OLD.request_hash OR NEW.user_id != OLD.user_id
                OR NEW.username_snapshot != OLD.username_snapshot OR NEW.total_cents != OLD.total_cents
                OR NEW.created_at_utc != OLD.created_at_utc OR OLD.status='VOIDED'
                OR NEW.status!='VOIDED'
            BEGIN SELECT RAISE(ABORT,'sale history is immutable'); END""",
        """CREATE TRIGGER sales_no_delete BEFORE DELETE ON sales
            BEGIN SELECT RAISE(ABORT,'sale history is immutable'); END""",
        """CREATE UNIQUE INDEX stock_movement_sale_once
            ON stock_movements(reference_type,reference_id,product_id,movement_type)
            WHERE reference_type='SALE' AND movement_type IN ('SALE','VOID')""",
    ):
        op.execute(statement)
    for table in ("sale_items", "payments"):
        for operation in ("UPDATE", "DELETE"):
            # Identificadores internos constantes, nunca valores recibidos por HTTP.
            op.execute(
                f"CREATE TRIGGER {table}_no_{operation.lower()} BEFORE {operation} ON {table} "
                "BEGIN SELECT RAISE(ABORT,'sale history is immutable'); END"
            )


def downgrade() -> None:
    raise RuntimeError("F4 no admite downgrade destructivo de ventas, pagos e historia")
