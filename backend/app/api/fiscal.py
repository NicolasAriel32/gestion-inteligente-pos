"""ADMIN y CSRF para diagnósticos fiscales, sin entrada HTTP de certificados o URLs."""
from typing import Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field, SecretStr

from app.api.catalog import Input
from app.api.identity import token

router = APIRouter(prefix='/fiscal', tags=['ARCA homologación'])


class Status(BaseModel):
    environment: Literal['homologation']
    emission_enabled: Literal[False]
    production_enabled: Literal[False]
    configured: bool
    configuration_error: str | None
    cuit: str | None
    certificate_fingerprint: str | None
    certificate_expires_at: str | None
    key_encrypted: bool


class Connection(BaseModel):
    environment: Literal['homologation']
    healthy: bool
    application: Literal['OK', 'NO']
    database: Literal['OK', 'NO']
    authentication: Literal['OK', 'NO']


class AccessInput(Input):
    private_key_password: SecretStr = Field(min_length=12, max_length=128)


class Point(BaseModel):
    number: int
    emission_type: str
    blocked: bool
    disabled_date: str | None


class Access(BaseModel):
    environment: Literal['homologation']
    authenticated: bool
    ticket_expires_at: str
    points: list[Point]


@router.get('/status', response_model=Status)
def status(request: Request) -> dict:
    return request.app.state.fiscal.status(token(request))


@router.post('/connection', response_model=Connection)
def connection(body: Input, request: Request) -> dict:
    return request.app.state.fiscal.connection(token(request, csrf=True))


@router.post('/access', response_model=Access)
def access(body: AccessInput, request: Request) -> dict:
    return request.app.state.fiscal.access(token(request, csrf=True), body.private_key_password.get_secret_value())
