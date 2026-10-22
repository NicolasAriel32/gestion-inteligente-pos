"""Valores y contratos de catálogo, independientes de HTTP y SQL."""

from dataclasses import dataclass
from typing import Any

MAX_INTEGER = 9_007_199_254_740_991
Record = dict[str, Any]


@dataclass(frozen=True)
class Category:
    id: int
    name: str
    is_active: bool


@dataclass(frozen=True)
class Product:
    id: int
    name: str
    code: str | None
    category_id: int | None
    price_cents: int
    cost_cents: int | None
    stock_quantity: int
    minimum_stock: int
    is_active: bool
    created_at: str
    updated_at: str
