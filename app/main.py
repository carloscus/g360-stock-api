from __future__ import annotations

import asyncio
import logging
import time
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.security import APIKeyHeader
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.middleware.gzip import GZipMiddleware

from app.config import settings
from app.routers import catalog, health, resumen, stock, upload
from app.services.catalog_service import catalog_service

logger = logging.getLogger("g360")

# ── Rate limiter ────────────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address, default_limits=[settings.rate_limit])


def _rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={"detail": f"Rate limit excedido: {exc.detail}"},
    )


# ── Auth ────────────────────────────────────────────────────────────
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def verificar_api_key(api_key: str = Depends(api_key_header)) -> None:
    if settings.api_key and api_key != settings.api_key:
        raise HTTPException(status_code=403, detail="API Key invalida")


def verificar_read_api_key(api_key: str = Depends(api_key_header)) -> None:
    """Allow the scoped read key or the legacy/admin key for compatibility."""
    allowed = {key for key in (settings.read_api_key, settings.api_key) if key}
    if allowed and api_key not in allowed:
        raise HTTPException(status_code=403, detail="API Key invalida")


# ── Lifespan ────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Iniciando G360 Stock API...")
    # Si el disco es efimero (Render free), el catalogo se pierde en cada
    # reinicio. Auto-cargarlo desde la fuente remota para nunca quedar vacio.
    if not catalog_service.cargado:
        try:
            resultado = await asyncio.to_thread(
                catalog_service.cargar_desde_url, settings.catalogo_raw_url
            )
            if resultado.get("ok"):
                logger.info("Catalogo auto-cargado: %s SKUs", resultado.get("total_skus"))
                from app.services.s1_service import servicio_stock
                servicio_stock.re_enriquecer()
            else:
                logger.warning("Auto-carga fallo: %s", resultado.get("error"))
        except (OSError, RuntimeError) as e:
            logger.exception("Auto-carga fallo inesperado: %s", e)
    yield
    logger.info("G360 Stock API detenida.")


# ── App ─────────────────────────────────────────────────────────────
app = FastAPI(
    title="G360 Stock API",
    description="API REST del reporte de stock S1 desde appweb.cipsa.com.pe. "
    "Provee acceso estructurado al stock, predespacho y disponible "
    "por producto y almacen para el ecosistema G360.",
    version="1.1.0",
    contact={
        "name": "G360 - CIPSA",
        "url": "https://github.com/carloscus",
    },
    lifespan=lifespan,
)

# ── Rate limiting ───────────────────────────────────────────────────
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_handler)

# ── Request logging + timeout ───────────────────────────────────────
@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    start = time.perf_counter()
    path = request.url.path
    method = request.method
    client = request.client.host if request.client else "unknown"

    try:
        response = await asyncio.wait_for(call_next(request), timeout=settings.request_timeout)
    except asyncio.TimeoutError:
        logger.warning("TIMEOUT %s %s (%ds) from %s", method, path, settings.request_timeout, client)
        return JSONResponse(
            status_code=504,
            content={"detail": "Request timeout"},
        )
    except Exception:
        logger.exception("ERROR %s %s from %s", method, path, client)
        raise

    elapsed = time.perf_counter() - start
    logger.info("%s %s %d %.3fs %s", method, path, response.status_code, elapsed, client)
    return response


# ── CORS ────────────────────────────────────────────────────────────
origins = [o.strip() for o in settings.cors_origins.split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=500)


# ── Root redirect ──────────────────────────────────────────────────
@app.get("/")
async def root():
    return RedirectResponse(url="/docs")


# ── Routers ─────────────────────────────────────────────────────────
# Lectura protegida con una clave de alcance reducido para GitHub Pages.
# Se acepta tambien la clave administrativa durante la transicion para no
# romper clientes existentes que ya consumen GET con X-API-Key.
app.include_router(health.router, dependencies=[Depends(verificar_read_api_key)])
app.include_router(stock.router, dependencies=[Depends(verificar_read_api_key)])
app.include_router(upload.router, dependencies=[Depends(verificar_api_key)])
app.include_router(resumen.router, dependencies=[Depends(verificar_api_key)])
app.include_router(catalog.router, dependencies=[Depends(verificar_api_key)])
