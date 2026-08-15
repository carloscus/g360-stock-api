from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.security import APIKeyHeader
from starlette.middleware.gzip import GZipMiddleware

from app.config import settings
from app.routers import catalog, health, resumen, stock, upload
from app.services.catalog_service import catalog_service

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def verificar_api_key(api_key: str = Depends(api_key_header)) -> None:
    if settings.api_key and api_key != settings.api_key:
        raise HTTPException(status_code=403, detail="API Key invalida")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Si el disco es efimero (Render free), el catalogo se pierde en cada
    # reinicio. Auto-cargarlo desde la fuente remota para nunca quedar vacio.
    if not catalog_service.cargado:
        try:
            resultado = await asyncio.to_thread(
                catalog_service.cargar_desde_url, settings.catalogo_raw_url
            )
            if resultado.get("ok"):
                print(f"[catalog] auto-cargado desde raw: {resultado.get('total_skus')} SKUs")
                # Re-enriquecer stock items con el catalogo recien cargado
                from app.services.s1_service import servicio_stock
                servicio_stock.re_enriquecer()
            else:
                print(f"[catalog] auto-carga fallo: {resultado.get('error')}")
        except (OSError, RuntimeError) as e:
            print(f"[catalog] auto-carga fallo inesperado: {e}")
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
app.add_middleware(GZipMiddleware, minimum_size=500)

app.include_router(health.router, dependencies=[Depends(verificar_api_key)])
app.include_router(stock.router, dependencies=[Depends(verificar_api_key)])
app.include_router(upload.router, dependencies=[Depends(verificar_api_key)])
app.include_router(resumen.router, dependencies=[Depends(verificar_api_key)])
app.include_router(catalog.router, dependencies=[Depends(verificar_api_key)])
