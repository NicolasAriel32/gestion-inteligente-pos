from logging.config import fileConfig

from alembic import context
from app.infrastructure.database import Base, build_engine, get_db_path

config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)
path = get_db_path()
config.set_main_option("sqlalchemy.url", f"sqlite:///{path}")
target_metadata = Base.metadata

def run_migrations_offline():
    context.configure(url=config.get_main_option("sqlalchemy.url"), target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online():
    engine = build_engine(path)
    with engine.connect() as connection:
        connection.exec_driver_sql("PRAGMA foreign_keys=ON")
        connection.exec_driver_sql("PRAGMA busy_timeout=5000")
        connection.exec_driver_sql("PRAGMA journal_mode=WAL")
        # Los PRAGMA abren una transacción implícita en SQLAlchemy 2.
        # Cerrarla permite que Alembic confirme su propia transacción.
        connection.commit()
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
