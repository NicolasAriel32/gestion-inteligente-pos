"""Contratos de venta sin dependencias de HTTP o persistencia."""

from typing import Literal, TypedDict

PaymentMethod = Literal["CASH", "TRANSFER", "DEBIT", "CREDIT"]
SaleStatus = Literal["COMPLETED", "VOIDED"]


class RequestedItem(TypedDict):
    product_id: int
    quantity: int
