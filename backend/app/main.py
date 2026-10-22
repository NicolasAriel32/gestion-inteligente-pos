"""Aplicación FastAPI local — F1."""
from fastapi import FastAPI
from starlette.middleware.trustedhost import TrustedHostMiddleware

app = FastAPI(title="Gestión Inteligente POS", version="0.1.0")
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost"])

@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
