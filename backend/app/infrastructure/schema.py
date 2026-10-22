"""Contrato mínimo de arranque: no migrar ni reparar datos automáticamente."""

from sqlalchemy import Engine, inspect, text
from sqlalchemy.exc import SQLAlchemyError

EXPECTED_REVISION = "0002_identity"
REQUIRED_COLUMNS = {
    "alembic_version": {"version_num"},
    "users": {"id", "username", "password_hash", "role", "is_active", "created_at"},
    "bootstrap": {"id", "token_hash", "expires_at", "completed"},
    "sessions": {"token_hash", "user_id", "expires_at"},
    "audit_log": {
        "id",
        "actor_id",
        "action",
        "entity_type",
        "entity_id",
        "event_data",
        "created_at_utc",
    },
}


class SchemaCompatibilityError(RuntimeError):
    """Base sin migrar, incompleta o de otra versión: no se habilita la aplicación."""


def verify_schema(engine: Engine) -> None:
    message = (
        "Esquema local incompatible. No se inició la aplicación. "
        "Verificá la versión instalada y el respaldo antes de ejecutar las migraciones. "
        "No borres la base ni cambies alembic_version manualmente."
    )
    try:
        with engine.connect() as connection:
            inspector = inspect(connection)
            if not REQUIRED_COLUMNS.keys() <= set(inspector.get_table_names()):
                raise SchemaCompatibilityError(message)
            for table, expected in REQUIRED_COLUMNS.items():
                actual = {column["name"] for column in inspector.get_columns(table)}
                if not expected <= actual:
                    raise SchemaCompatibilityError(message)
            revisions = connection.execute(text("SELECT version_num FROM alembic_version")).all()
            if revisions != [(EXPECTED_REVISION,)]:
                raise SchemaCompatibilityError(message)
    except SQLAlchemyError:
        raise SchemaCompatibilityError(message) from None
