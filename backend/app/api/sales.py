"""Contratos de caja: el cliente solo elige productos, cantidades y medio declarado."""

from typing import Annotated, Self
from uuid import UUID

from fastapi import APIRouter, Query, Request
from fastapi import Path as ApiPath
from pydantic import BaseModel, Field, StringConstraints, model_validator

from app.api.catalog import Input, PositiveId, Reason
from app.api.identity import token
from app.application.sales import SalesService
from app.domain.catalog import MAX_INTEGER, Record
from app.domain.sales import PaymentMethod, RequestedItem, SaleStatus

router = APIRouter()


class Item(Input):
    product_id: PositiveId
    quantity: PositiveId


class Cart(Input):
    items: Annotated[list[Item], Field(min_length=1, max_length=100)]

    @model_validator(mode="after")
    def distinct_products(self) -> Self:
        if len({item.product_id for item in self.items}) != len(self.items):
            raise ValueError("No repetir productos en el carrito")
        return self

    def requested(self) -> list[RequestedItem]:
        return [{"product_id": item.product_id, "quantity": item.quantity} for item in self.items]


class Checkout(Cart):
    payment_method: PaymentMethod
    idempotency_key: UUID
    quote_fingerprint: Annotated[str, StringConstraints(strict=True, pattern=r"^[0-9a-f]{64}$")]


class Void(Input):
    reason: Reason


class LineOut(BaseModel):
    product_id: int
    product_name_snapshot: str
    product_code_snapshot: str | None
    unit_price_cents: int
    quantity: int
    subtotal_cents: int


class QuoteOut(BaseModel):
    items: list[LineOut]
    total_cents: int
    quote_fingerprint: str


class PaymentOut(BaseModel):
    method: PaymentMethod
    amount_cents: int


class SummaryOut(BaseModel):
    id: int
    user_id: int
    username_snapshot: str
    status: SaleStatus
    total_cents: int
    created_at_utc: str
    payment_method: PaymentMethod


class SaleOut(BaseModel):
    id: int
    user_id: int
    username_snapshot: str
    status: SaleStatus
    total_cents: int
    created_at_utc: str
    voided_at_utc: str | None
    voided_by: int | None
    void_reason: str | None
    items: list[LineOut]
    payment: PaymentOut


class SalePage(BaseModel):
    items: list[SummaryOut]
    total: int


def service(request: Request) -> SalesService:
    return request.app.state.sales


@router.post("/sales/quote", response_model=QuoteOut)
def quote(body: Cart, request: Request) -> Record:
    return service(request).quote(token(request, csrf=True), body.requested())


@router.post("/sales", status_code=201, response_model=SaleOut)
def checkout(body: Checkout, request: Request) -> Record:
    return service(request).create(token(request, csrf=True), body.requested(), body.payment_method, str(body.idempotency_key), body.quote_fingerprint)


@router.get("/sales", response_model=SalePage)
def history(request: Request, user_id: int | None = Query(None, gt=0, le=MAX_INTEGER), status: SaleStatus | None = None, limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0, le=MAX_INTEGER)) -> Record:
    return service(request).sales(token(request), user_id, status, limit, offset)


@router.get("/sales/{sale_id}", response_model=SaleOut)
def detail(sale_id: Annotated[int, ApiPath(gt=0, le=MAX_INTEGER)], request: Request) -> Record:
    return service(request).sale(token(request), sale_id)


@router.post("/sales/{sale_id}/void", response_model=SaleOut)
def void(sale_id: Annotated[int, ApiPath(gt=0, le=MAX_INTEGER)], body: Void, request: Request) -> Record:
    return service(request).void(token(request, csrf=True), sale_id, body.reason)
