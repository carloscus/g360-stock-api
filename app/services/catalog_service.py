"""
Catalog Service - Carga y gestión del catálogo maestro de productos.
Lee el catálogo JSON generado por g360-master-data y lo mantiene en memoria.
"""
from __future__ import annotations

import json
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.config import settings


class CatalogService:
    """Maneja el catálogo de productos en memoria con TTL."""

    def __init__(self):
        self._lock = threading.Lock()
        self._catalog: dict[str, dict] = {}
        self._fecha_carga: datetime | None = None
        self._ruta_cache = Path(settings.catalogo_ruta)

        # Cargar al iniciar
        self._cargar_si_existe()

    def _cargar_si_existe(self) -> bool:
        """Carga el catálogo desde disco si existe y no ha expirado."""
        with self._lock:
            if not self._ruta_cache.exists():
                return False

            try:
                payload = json.loads(self._ruta_cache.read_text(encoding="utf-8"))
                productos = payload.get("productos", [])
                fecha_str = payload.get("metadata", {}).get("generated_at")

                # Construir mapa por SKU
                catalog = {}
                for p in productos:
                    sku = p.get("sku", "").strip()
                    if sku:
                        catalog[sku] = p

                self._catalog = catalog
                if fecha_str:
                    self._fecha_carga = datetime.fromisoformat(fecha_str)
                    if self._fecha_carga.tzinfo is None:
                        self._fecha_carga = self._fecha_carga.replace(tzinfo=timezone.utc)
                else:
                    self._fecha_carga = datetime.now(timezone.utc)

                return True
            except (json.JSONDecodeError, OSError):
                return False

    @property
    def cargado(self) -> bool:
        return bool(self._catalog)

    @property
    def total_skus(self) -> int:
        return len(self._catalog)

    @property
    def edad_segundos(self) -> int:
        if not self._fecha_carga:
            return 0
        return int((datetime.now(timezone.utc) - self._fecha_carga).total_seconds())

    @property
    def stale(self) -> bool:
        if not self._fecha_carga:
            return True
        return (datetime.now(timezone.utc) - self._fecha_carga) > timedelta(seconds=settings.catalogo_ttl_segundos)

    def buscar(self, sku: str) -> dict | None:
        """Busca un SKU en el catálogo."""
        return self._catalog.get(sku.strip().upper())

    @property
    def fecha_carga(self) -> datetime | None:
        """Momento en que se cargó el catálogo."""
        return self._fecha_carga

    def listar(self) -> list[dict]:
        """Devuelve el catálogo completo ordenado por 'orden' del maestro y luego por SKU."""
        with self._lock:
            items = list(self._catalog.values())
        items.sort(key=lambda p: (p.get("orden") is None, p.get("orden") or 9999, p.get("sku") or ""))
        return items

    def cargar_desde_url(self, url: str) -> dict:
        """Descarga el catalogo desde una URL remota y lo carga en memoria."""
        import httpx

        try:
            respuesta = httpx.get(url, timeout=30)
            respuesta.raise_for_status()
            data = respuesta.json()
        except (httpx.TimeoutException, httpx.NetworkError, httpx.HTTPStatusError, json.JSONDecodeError) as e:
            return {"ok": False, "error": f"No se pudo descargar el catalogo: {e}", "total_skus": 0}

        resultado = self.cargar_desde_json(data)
        resultado["ok"] = True
        return resultado

    def cargar_desde_json(self, data: dict) -> dict:
        """Carga un catálogo desde un dict (usado por upload)."""
        with self._lock:
            productos = data.get("productos", [])
            catalog = {}
            for p in productos:
                sku = p.get("sku", "").strip()
                if sku:
                    catalog[sku] = p
            self._catalog = catalog
            self._fecha_carga = datetime.now(timezone.utc)
            self._guardar_en_disco()
            return {
                "total_skus": len(catalog),
                "con_ean14": sum(1 for p in catalog.values() if p.get("ean14")),
                "con_unbx": sum(1 for p in catalog.values() if p.get("un_bx", 1) > 1),
            }

    def _guardar_en_disco(self) -> None:
        """Persiste el catálogo en disco para sobreviver reinicios."""
        try:
            self._ruta_cache.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "metadata": {
                    "generated_at": self._fecha_carga.isoformat() if self._fecha_carga else None,
                    "total_productos": len(self._catalog),
                },
                "productos": list(self._catalog.values()),
            }
            # Backup rotativo
            bak = self._ruta_cache.with_suffix(".bak.json")
            if self._ruta_cache.exists():
                self._ruta_cache.rename(bak)
            self._ruta_cache.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except OSError:
            pass

    def health(self) -> dict:
        return {
            "cargado": self.cargado,
            "total_skus": self.total_skus,
            "edad_segundos": self.edad_segundos,
            "stale": self.stale,
            "ttl_segundos": settings.catalogo_ttl_segundos,
        }


# Instancia global
catalog_service = CatalogService()
