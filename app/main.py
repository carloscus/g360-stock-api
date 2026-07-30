from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.security import APIKeyHeader

from app.config import settings
from app.routers import health, stock, upload, resumen

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def verificar_api_key(api_key: str = Depends(api_key_header)) -> None:
    if settings.api_key and api_key != settings.api_key:
        raise HTTPException(status_code=403, detail="API Key invalida")


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(
    title="G360 Stock API",
    description="API REST del reporte de stock S1 desde appweb.cipsa.com.pe. "
    "Provee acceso estructurado al stock, predespacho y disponible "
    "por producto y almacen para el ecosistema G360.",
    version="1.0.0",
    contact={
        "name": "G360 - CIPSA",
        "url": "https://github.com/carloscus",
    },
    lifespan=lifespan,
)

@app.get("/")
async def root():
    return RedirectResponse(url="/docs")


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, dependencies=[Depends(verificar_api_key)])
app.include_router(stock.router, dependencies=[Depends(verificar_api_key)])
app.include_router(upload.router, dependencies=[Depends(verificar_api_key)])
app.include_router(resumen.router, dependencies=[Depends(verificar_api_key)])
