"""Autorización antes de red; sin transacciones SQLite abiertas durante SOAP."""
from collections.abc import Callable

from app.application.identity import Store, digest
from app.domain.catalog import Record
from app.domain.fiscal import FiscalGateway
from app.domain.identity import IdentityError


class FiscalService:
    def __init__(self, store: Store, gateway: FiscalGateway, clock: Callable[[], float]):
        self.store, self.gateway, self.clock = store, gateway, clock

    def admin(self, token: str) -> None:
        with self.store.transaction() as tx:
            actor = tx.session_user(digest(token), int(self.clock()))
            if actor.role != 'ADMIN':
                raise IdentityError(403, 'Se requiere rol ADMIN')

    def status(self, token: str) -> Record:
        self.admin(token)
        return self.gateway.status()

    def connection(self, token: str) -> Record:
        self.admin(token)
        return self.gateway.connection()

    def access(self, token: str, password: str) -> Record:
        self.admin(token)
        return self.gateway.access(password)
