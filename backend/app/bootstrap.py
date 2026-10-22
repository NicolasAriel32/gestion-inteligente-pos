"""Entrega local de un secreto de instalación; nunca imprime su contenido."""

import argparse
import os
import secrets
import tempfile
import time
from pathlib import Path

from app.application.identity import digest
from app.domain.identity import IdentityError
from app.infrastructure.database import build_engine, get_db_path
from app.infrastructure.identity import IdentityStore


def prepare_setup(path: Path, renew: bool = False) -> Path:
    engine = build_engine(path)
    secret_file = path.parent.parent / "config" / "setup-token.txt"
    try:
        with IdentityStore(engine).transaction(write=True) as tx:
            if tx.initialized():
                raise IdentityError(409, "La inicialización ya fue completada")
            if tx.bootstrap() and not renew:
                raise IdentityError(409, "Ya existe un secreto; usar --renew para reemplazarlo")
            token = secrets.token_urlsafe(32)
            secret_file.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            descriptor, temporary = tempfile.mkstemp(dir=secret_file.parent)
            try:
                with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                    stream.write(token)
                os.replace(temporary, secret_file)
            finally:
                Path(temporary).unlink(missing_ok=True)
            tx.prepare_setup(digest(token), int(time.time()) + 1800)
        return secret_file
    finally:
        engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--renew", action="store_true", help="Revocar secreto pendiente y generar otro"
    )
    args = parser.parse_args()
    try:
        path = prepare_setup(get_db_path(), args.renew)
    except IdentityError as exc:
        parser.exit(1, str(exc) + "\n")
    print(f"Secreto de inicialización guardado en: {path}")
    print("Abrí el archivo localmente, usalo en el formulario y eliminá el archivo al terminar.")


if __name__ == "__main__":
    main()
