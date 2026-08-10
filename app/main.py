from __future__ import annotations

import asyncio
import gzip
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.security import APIKeyHeader
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.config import settings
from app.routers import catalog, health, resumen, stock, upload
from app.services.catalog_service import catalog_service

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def verificar_api_key(api_key: str = Depends(api_key_header)) -> None:
    if settings.api_key and api_key != settings.api_key:
        raise HTTPException(status_code=403, detail="API Key invalida")


class CompressionMiddleware(BaseHTTPMiddleware):
    """Compress responses with gzip or brotli based on Accept-Encoding header."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        
        # Skip compression for small responses
        content_length = response.headers.get("content-length")
        if content_length and int(content_length) < 500:
            return response
        
        # Skip if already compressed
        if "content-encoding" in response.headers:
            return response
        
        accept_encoding = request.headers.get("accept-encoding", "")
        
        # Read body
        body = b"".join([chunk async for chunk in response.body_iterator])
        
        # Try brotli first (better compression)
        if "br" in accept_encoding:
            try:
                import brotli
                compressed = brotli.compress(body)
                return Response(
                    content=compressed,
                    status_code=response.status_code,
                    headers={
                        **dict(response.headers),
                        "content-encoding": "br",
                        "content-length": str(len(compressed)),
                        "vary": "accept-encoding",
                    },
                )
            except Exception:
                pass
        
        # Fall back to gzip
        if "gzip" in accept_encoding:
            try:
                import gzip
                compressed = gzip.compress(body)
                return Response(
                    content=compressed,
                    status_code=response.status_code,
                    headers={
                        **dict(response.headers),
                        "content-encoding": "gzip",
                        "content-length": str(len(compressed)),
                        "vary": "accept-encoding",
                    },
                )
            except Exception:
                pass
        
        # Return uncompressed
        return Response(
            content=body,
            status_code=response.status_code,
            headers=dict(response.headers),
        )


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
app.add_middleware(CompressionMiddleware)

app.include_router(health.router, dependencies=[Depends(verificar_api_key)])
app.include_router(stock.router, dependencies=[Depends(verificar_api_key)])
app.include_router(upload.router, dependencies=[Depends(verificar_api_key)])
app.include_router(resumen.router, dependencies=[Depends(verificar_api_key)])
app.include_router(catalog.router, dependencies=[Depends(verificar_api_key)])
