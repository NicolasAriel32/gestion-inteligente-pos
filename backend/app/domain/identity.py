"""Contratos de identidad independientes de HTTP y SQLite."""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class User:
    id: int
    username: str
    role: str
    is_active: bool


class IdentityError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


class Passwords(Protocol):
    def hash(self, password: str) -> str: ...
    def verify(self, encoded: str, password: str) -> bool: ...
