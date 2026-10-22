"""Índice aditivo para reportes globales por estado y fecha UTC."""

from alembic import op

revision = "0005_reporting_indexes"
down_revision = "0004_checkout_history"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE INDEX sales_report_date ON sales(status,created_at_utc,id,total_cents)")


def downgrade() -> None:
    raise RuntimeError("Usar upgrade explícito; no realizar downgrade automático")
