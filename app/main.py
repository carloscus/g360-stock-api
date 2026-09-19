from __future__ import annotations

import asyncio
import logging
import threading
import time
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.security import APIKeyHeader
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.gzip import GZipMiddleware
from starlette.requests import Request as StarletteRequest
from starlette.responses import Response as StarletteResponse
from starlette.types import ASGIApp

from app.config import settings
from app.routers import catalog, health, resumen, stock, upload
from app.services.catalog_service import catalog_service

logger = logging.getLogger("g360")

# Rutas exentas del rate limit (health checks de Render y docs publicos)
_RUTAS_EXENTAS_RATE_LIMIT = ("/api/v1/health", "/docs", "/redoc", "/openapi.json")


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiter por IP con ventana fija.

    Nota: no usamos slowapi porque su SlowAPIMiddleware no encuentra los
    handlers de FastAPI >= 0.115 (los routers viven en _IncludedRouter con
    endpoint=None), por lo que los limites nunca se aplicaban.
    Esta implementacion es autocontenida y no depende de introspeccion de rutas.
    """

    def __init__(self, app: ASGIApp, limite: str = "60/minute", global_limite: str = "150/minute"):
        super().__init__(app)
        self._max, self._ventana = self._parsear_limite(limite)
        self._global_max, self._global_ventana = self._parsear_limite(global_limite)
        self._ventanas: dict[str, tuple[float, int]] = {}
        self._global_ventana_state: tuple[float, int] = (0.0, 0)
        self._lock = threading.Lock()

    @staticmethod
    def _parsear_limite(limite: str) -> tuple[int, int]:
        """Convierte '60/minute' en (60, 60). Soporta second/minute/hour."""
        cantidad, _, periodo = limite.partition("/")
        max_req = int(cantidad.strip())
        segundos = {"second": 1, "minute": 60, "hour": 3600}.get(
            periodo.strip().lower(), 60
        )
        return max_req, segundos

    @staticmethod
    def _ip_cliente(request: StarletteRequest) -> str:
        """IP real del cliente.

        Detras de Render/Cloudflare, request.client.host es la IP del proxy
        interno (varia por request segun el pool) y NO sirve como clave de
        ventana. Se usa X-Forwarded-For (primer salto, seteado por el edge
        confiable) con fallback a X-Real-IP y finalmente client.host.
        """
        xff = request.headers.get("x-forwarded-for")
        if xff:
            primer = xff.split(",")[0].strip()
            if primer:
                return primer
        xr = request.headers.get("x-real-ip")
        if xr:
            return xr.strip()
        return request.client.host if request.client else "unknown"

    async def dispatch(
        self, request: StarletteRequest, call_next
    ) -> StarletteResponse:
        path = request.url.path
        if any(path.startswith(exenta) for exenta in _RUTAS_EXENTAS_RATE_LIMIT):
            return await call_next(request)

        ip = self._ip_cliente(request)
        ahora = time.monotonic()
        permitido = True
        razon = ""
        with self._lock:
            # Tope global primero: una sola clave, determinista incluso si
            # el proxy rota la IP percibida. Protege CPU/costos de Render.
            g_inicio, g_conteo = self._global_ventana_state
            if ahora - g_inicio >= self._global_ventana:
                g_inicio, g_conteo = ahora, 0
            g_conteo += 1
            self._global_ventana_state = (g_inicio, g_conteo)
            if g_conteo > self._global_max:
                permitido = False
                razon = "global"
            else:
                # Por IP: primera capa (mejor esfuerzo detras de proxy)
                inicio, conteo = self._ventanas.get(ip, (ahora, 0))
                if ahora - inicio >= self._ventana:
                    inicio, conteo = ahora, 0
                conteo += 1
                self._ventanas[ip] = (inicio, conteo)
                if len(self._ventanas) > 10_000:
                    self._ventanas = {
                        k: v for k, v in self._ventanas.items()
                        if ahora - v[0] < self._ventana
                    }
                if conteo > self._max:
                    permitido = False
                    razon = "ip"

        if not permitido:
            logger.warning("RATE LIMIT excedido (%s) por %s en %s", razon, ip, path)
            ventana = self._global_ventana if razon == "global" else self._ventana
            return JSONResponse(
                status_code=429,
                content={"detail": f"Rate limit excedido: {ventana}s"},
                headers={"Retry-After": str(ventana)},
            )
        return await call_next(request)


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
    description="API REST de datos de stock. Procesa reportes desde la fuente "
    "del cliente, los transforma y sirve enriquecidos con catálogo maestro. "
    "Provee acceso estructurado al stock, predespacho y disponible "
    "por producto y almacen para el ecosistema G360.",
    version="1.4.0",
    contact={
        "name": "G360 - CIPSA",
        "url": "https://github.com/carloscus",
    },
    lifespan=lifespan,
)

# ── Rate limiting ───────────────────────────────────────────────────
# Dos capas: por IP (mejor esfuerzo detras de proxy) + tope global
# determinista que protege CPU/costos. /api/v1/health y docs exentos.
app.add_middleware(
    RateLimitMiddleware,
    limite=settings.rate_limit,
    global_limite=settings.global_rate_limit,
)

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
# /api/v1/health es publico (sin API key) para que el healthcheck de
# Render funcione (Render no puede enviar headers custom). Solo expone
# estado del cache. El resto de GET de lectura usa la clave de alcance
# reducido; tambien se acepta la clave administrativa durante la transicion
# para no romper clientes existentes que ya consumen GET con X-API-Key.
app.include_router(health.router)
app.include_router(stock.router, dependencies=[Depends(verificar_read_api_key)])
app.include_router(upload.router, dependencies=[Depends(verificar_api_key)])
app.include_router(resumen.router, dependencies=[Depends(verificar_api_key)])
app.include_router(catalog.router, dependencies=[Depends(verificar_api_key)])
