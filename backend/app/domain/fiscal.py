"""Contratos fiscales del incremento de conexión; sin emisión ni producción."""
from typing import Protocol

from app.domain.catalog import Record
from app.domain.identity import IdentityError


def validate_cuit(value: str) -> str:
    if len(value) != 11 or not value.isascii() or not value.isdigit():
        raise IdentityError(422, 'CUIT inválido: ingresá 11 dígitos sin guiones')
    total = sum(int(digit) * weight for digit, weight in zip(value[:10], (5, 4, 3, 2, 7, 6, 5, 4, 3, 2)))
    if (total + int(value[-1])) % 11 != 0 or value == '00000000000':
        raise IdentityError(422, 'Dígito verificador del CUIT inválido')
    return value


class FiscalGateway(Protocol):
    def status(self) -> Record: ...
    def connection(self) -> Record: ...
    def access(self, password: str) -> Record: ...
