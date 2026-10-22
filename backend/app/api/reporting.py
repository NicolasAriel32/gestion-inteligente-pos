"""Contrato único para KPIs, comparación, rankings y horas consistentes."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from app.api.identity import token
from app.domain.catalog import Record
from app.domain.reporting import Period

router = APIRouter()
Unsigned = Annotated[str, Field(pattern=r"^(0|[1-9][0-9]*)$")]
Signed = Annotated[str, Field(pattern=r"^-?(0|[1-9][0-9]*)$")]


class IntervalOut(BaseModel):
    start_utc: str
    end_utc: str
    start_local: str
    end_local: str


class Metrics(BaseModel):
    revenue_cents: Unsigned
    sales: Unsigned
    units: Unsigned
    average_cents: Unsigned


class Change(BaseModel):
    delta: Signed
    percent_bp: Signed | None


class Changes(BaseModel):
    revenue_cents: Change
    sales: Change
    units: Change
    average_cents: Change


class ProductRank(BaseModel):
    product_id: int
    name: str
    code: str | None
    units: Unsigned
    revenue_cents: Unsigned


class Hour(BaseModel):
    hour: Annotated[int, Field(ge=0, le=23)]
    sales: Unsigned
    revenue_cents: Unsigned


class Report(BaseModel):
    timezone: str
    period: IntervalOut
    previous_period: IntervalOut
    current: Metrics
    previous: Metrics
    comparison: Changes
    top_units: list[ProductRank]
    top_revenue: list[ProductRank]
    hours: list[Hour]
    peak_hours: list[int]


@router.get("/reports/summary", response_model=Report)
def summary(request: Request, period: Period = "today", start: date | None = None, end: date | None = None) -> Record:
    return request.app.state.reporting.summary(token(request), period, start, end)
