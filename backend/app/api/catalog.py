"""HTTP F3: JSON estricto, importes enteros y ningún campo de stock en PATCH."""

from typing import Annotated, Self
from uuid import UUID

from fastapi import APIRouter, Query, Request
from fastapi import Path as ApiPath
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictInt,
    StringConstraints,
    field_validator,
    model_validator,
)

from app.api.identity import token
from app.application.catalog import CatalogService
from app.domain.catalog import MAX_INTEGER, Category, Product, Record

router = APIRouter()
Name = Annotated[
    str, StringConstraints(strict=True, strip_whitespace=True, min_length=1, max_length=160)
]
CategoryName = Annotated[
    str, StringConstraints(strict=True, strip_whitespace=True, min_length=1, max_length=100)
]
Reason = Annotated[
    str, StringConstraints(strict=True, strip_whitespace=True, min_length=3, max_length=240)
]
Amount = Annotated[StrictInt, Field(ge=0, le=MAX_INTEGER)]
PositiveId = Annotated[StrictInt, Field(gt=0, le=MAX_INTEGER)]
Code = Annotated[str, StringConstraints(strict=True, strip_whitespace=True, max_length=64)]


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CategoryCreate(Input):
    name: CategoryName


class CategoryPatch(Input):
    name: CategoryName | None = None
    is_active: StrictBool | None = None

    @model_validator(mode="after")
    def valid_patch(self) -> Self:
        if not self.model_fields_set or any(
            getattr(self, key) is None for key in self.model_fields_set
        ):
            raise ValueError("Edición vacía o con null no admitido")
        return self


class ProductBase(Input):
    name: Name
    code: Code | None = None
    category_id: PositiveId | None = None
    price_cents: Amount
    cost_cents: Amount | None = None
    minimum_stock: Amount = 0

    @field_validator("code")
    @classmethod
    def blank_code(cls, value: str | None) -> str | None:
        return value or None


class ProductCreate(ProductBase):
    initial_stock: Amount = 0
    initial_reason: Reason | None = None


class ProductPatch(Input):
    name: Name | None = None
    code: Code | None = None
    category_id: PositiveId | None = None
    price_cents: Amount | None = None
    cost_cents: Amount | None = None
    minimum_stock: Amount | None = None
    is_active: StrictBool | None = None

    @field_validator("code")
    @classmethod
    def blank_code(cls, value: str | None) -> str | None:
        return value or None

    @model_validator(mode="after")
    def valid_patch(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("Edición vacía")
        for key in self.model_fields_set - {"code", "category_id", "cost_cents"}:
            if getattr(self, key) is None:
                raise ValueError("null no admitido")
        return self


class Adjustment(Input):
    product_id: PositiveId
    quantity_delta: Annotated[StrictInt, Field(ge=-MAX_INTEGER, le=MAX_INTEGER)]
    reason: Reason
    idempotency_key: UUID

    @field_validator("quantity_delta")
    @classmethod
    def nonzero(cls, value: int) -> int:
        if value == 0:
            raise ValueError("El ajuste debe cambiar existencias")
        return value


class CategoryOut(BaseModel):
    id: int
    name: str
    is_active: bool


class ProductOut(BaseModel):
    id: int
    name: str
    code: str | None
    category_id: int | None
    price_cents: int
    cost_cents: int | None
    minimum_stock: int
    stock_quantity: int
    is_active: bool
    created_at: str
    updated_at: str


class ProductPage(BaseModel):
    items: list[ProductOut]
    total: int


class MovementOut(BaseModel):
    id: int
    product_id: int
    movement_type: str
    quantity_delta: int
    stock_before: int
    stock_after: int
    reference_type: str
    reference_id: int
    performed_by: int
    reason: str
    request_key: str | None
    created_at_utc: str


class MovementPage(BaseModel):
    items: list[MovementOut]
    total: int


def service(request: Request) -> CatalogService:
    return request.app.state.catalog


@router.get("/categories", response_model=list[CategoryOut])
def categories(request: Request) -> list[Category]:
    return service(request).categories(token(request))


@router.post("/categories", status_code=201, response_model=CategoryOut)
def create_category(body: CategoryCreate, request: Request) -> Category:
    return service(request).save_category(token(request, csrf=True), body.model_dump())


@router.patch("/categories/{category_id}", response_model=CategoryOut)
def update_category(
    category_id: Annotated[int, ApiPath(gt=0, le=MAX_INTEGER)],
    body: CategoryPatch,
    request: Request,
) -> Category:
    return service(request).save_category(
        token(request, csrf=True), body.model_dump(exclude_unset=True), category_id
    )


@router.get("/products", response_model=ProductPage)
def products(
    request: Request,
    search: str = Query("", max_length=160),
    category_id: int | None = Query(None, gt=0, le=MAX_INTEGER),
    active_only: bool = True,
    low_stock: bool = False,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0, le=MAX_INTEGER),
) -> Record:
    return service(request).products(
        token(request),
        search=search,
        category_id=category_id,
        active_only=active_only,
        low_stock=low_stock,
        limit=limit,
        offset=offset,
    )


@router.get("/products/{product_id}", response_model=ProductOut)
def product(product_id: Annotated[int, ApiPath(gt=0, le=MAX_INTEGER)], request: Request) -> Product:
    return service(request).product(token(request), product_id)


@router.post("/products", status_code=201, response_model=ProductOut)
def create_product(body: ProductCreate, request: Request) -> Product:
    return service(request).create_product(token(request, csrf=True), body.model_dump())


@router.patch("/products/{product_id}", response_model=ProductOut)
def update_product(
    product_id: Annotated[int, ApiPath(gt=0, le=MAX_INTEGER)], body: ProductPatch, request: Request
) -> Product:
    return service(request).update_product(
        token(request, csrf=True), product_id, body.model_dump(exclude_unset=True)
    )


@router.post("/stock/adjustments", status_code=201, response_model=MovementOut)
def adjustment(body: Adjustment, request: Request) -> Record:
    return service(request).adjust(
        token(request, csrf=True),
        body.product_id,
        body.quantity_delta,
        body.reason,
        str(body.idempotency_key),
    )


@router.get("/stock/movements", response_model=MovementPage)
def movements(
    request: Request,
    product_id: int | None = Query(None, gt=0, le=MAX_INTEGER),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0, le=MAX_INTEGER),
) -> Record:
    return service(request).movements(token(request), product_id, limit, offset)
