from __future__ import annotations

import json
import logging
import re
import shutil
import tempfile
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import httpx

from app.config import settings
from app.core.constants import (
    ENCABEZADOS_HTTP,
    ALMACEN_PRINCIPAL,
    ALMACENES_MKTD,
    asignar_categoria,
)
from app.core.parsers import parsear_stock_desde_xls
from app.models.schemas import (
    AlmacenStock,
    ItemStock,
    ItemStockEnriched,
    MetadataStock,
    StockEnrichedResponse,
    ResumenStock,
    HealthResponse,
)
from app.services.catalog_service import catalog_service

logger = logging.getLogger(__name__)

LIMA_TZ = timezone(timedelta(hours=-5))

_PLACEHOLDERS = frozenset({"", "TODOS"})

# Regex consolidados para linea
_RE_2CHAR = re.compile(r'^([0-9A-Z]{2})$')
_RE_4DIGIT = re.compile(r'^01([0-9]{2})$')
_RE_4ALNUM = re.compile(r'^01([0-9A-Z]+)$')
_RE_4ALNUM_DASH = re.compile(r'^01([0-9A-Z]+)\s*-\s*(.+)$')
_RE_ANY_DASH = re.compile(r'^([0-9A-Z]{2,4})\s*-')


def _a_lima(dt: Optional[datetime]) -> Optional[datetime]:
    """Convierte un datetime UTC a zona Lima (-05:00) para display al usuario."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(LIMA_TZ)


def _normalizar_linea(linea: str) -> str:
    """Normaliza el formato de la linea para display.
    Maneja: '0101' -> '01', '0101 - PELOTAS' -> '01 - PELOTAS',
    '01AD - ACCESORIOS' -> 'AD - ACCESORIOS', '01 - PELOTAS' -> '01 - PELOTAS'
    """
    if not linea:
        return ""
    # '0101' -> '01'
    m = _RE_4DIGIT.match(linea)
    if m:
        return m.group(1)
    # '01AD' -> 'AD'
    m = _RE_4ALNUM.match(linea)
    if m:
        suffix = m.group(1)
        return suffix[:2] if suffix[0].isdigit() else suffix
    # '0101 - PELOTAS' or '01AD - ACCESORIOS'
    m = _RE_4ALNUM_DASH.match(linea)
    if m:
        suffix = m.group(1)
        rest = m.group(2).strip()
        return f"{suffix[:2]} - {rest}" if suffix[0].isdigit() else f"{suffix} - {rest}"
    # '01 - PELOTAS' or 'AD - ACCESORIOS'
    if _RE_ANY_DASH.match(linea):
        return linea
    return linea


def _extraer_linea_id(linea: str) -> Optional[str]:
    """Extrae el identificador corto de la linea a partir del codigo.
    Soporta: '0101' -> '01', '0101 - PELOTAS' -> '01',
    'AD - ACCESORIOS' -> 'AD', '78' -> '78', 'MA' -> 'MA'
    """
    if not linea:
        return None
    m = _RE_2CHAR.match(linea)
    if m:
        return m.group(1)
    m = _RE_4DIGIT.match(linea)
    if m:
        return m.group(1)
    m = _RE_4ALNUM.match(linea)
    if m:
        suffix = m.group(1)
        return suffix[:2] if suffix[0].isdigit() else suffix
    m = _RE_4ALNUM_DASH.match(linea)
    if m:
        suffix = m.group(1)
        return suffix[:2] if suffix[0].isdigit() else suffix
    m = _RE_ANY_DASH.match(linea)
    if m:
        return m.group(1)
    return None


def _tipo_almacen(codigo: str) -> str:
    if codigo in ALMACENES_MKTD or codigo.upper().startswith("S"):
        return "mktd"
    return "venta"


class ServicioStock:
    def __init__(self):
        self._lock = threading.Lock()
        # Fuente general
        self._datos_general: dict[str, dict[str, dict]] = {}
        self._items_general: list[ItemStock] = []
        self._enriched_general: list[ItemStockEnriched] = []
        self._fecha_general: Optional[datetime] = None
        # Fuente sucursales
        self._datos_sucursales: dict[str, dict[str, dict]] = {}
        self._items_sucursales: list[ItemStock] = []
        self._enriched_sucursales: list[ItemStockEnriched] = []
        self._fecha_sucursales: Optional[datetime] = None
        # Fuente combinada
        self._enriched_todas: list[ItemStockEnriched] = []
        # Circuit breaker
        self._cb_fallos_general: int = 0
        self._cb_fallos_sucursales: int = 0
        self._cb_abierto_general: Optional[datetime] = None
        self._cb_abierto_sucursales: Optional[datetime] = None

        self._cargar_cache(settings.cache_ruta, "general")
        self._cargar_cache(settings.cache_ruta2, "sucursales")
        self._enriquecer_todo()

    # ── Metodos publicos ────────────────────────────────────────────────

    def obtener_stock(
        self,
        almacen: Optional[str] = None,
        busqueda: Optional[str] = None,
        linea: Optional[str] = None,
        grupo: Optional[str] = None,
        um: Optional[str] = None,
        categoria: Optional[str] = None,
        tipo: Optional[str] = None,
        fuente: str = "general",
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> StockEnrichedResponse:
        # Si se filtra por almacen y no se especifica fuente, usar todas para detectar S*
        if almacen and fuente == "general":
            fuente = "todas"
        self._refrescar_si_es_necesario(fuente)
        items = self._obtener_enriched_segun_fuente(fuente)
        return self._construir_respuesta(items, fuente, almacen, busqueda, linea, grupo, um, categoria, limit, offset, tipo=tipo)

    def obtener_sku_enriched(self, sku: str, fuente: str = "general") -> Optional[ItemStockEnriched]:
        # Auto-detect: si la fuente es general pero el SKU existe en sucursales, usar todas
        if fuente == "general":
            self._refrescar_si_es_necesario("sucursales")
            if any(i.sku == sku for i in self._items_sucursales):
                fuente = "todas"
        self._refrescar_si_es_necesario(fuente)
        items = self._obtener_enriched_segun_fuente(fuente)
        mapa = {i.sku: i for i in items}
        return mapa.get(sku)

    def re_enriquecer(self) -> None:
        """Re-enriquece todos los items con el catalogo actual.
        Llamar despues de cargar/recargar el catalogo."""
        self._enriquecer_todo()

    def obtener_resumen(self) -> ResumenStock:
        self._refrescar_si_es_necesario("general")
        return self._calcular_resumen()

    def obtener_health(self) -> HealthResponse:
        ahora = datetime.now(timezone.utc)
        valido = bool(self._fecha_general and ahora - self._fecha_general <= timedelta(seconds=settings.cache_ttl_segundos))
        return HealthResponse(
            status="ok",
            timestamp=_a_lima(ahora),
            cache_skus=len(self._items_general),
            cache_valido=valido,
        )

    def procesar_archivo_local(self, ruta: str, fuente: str = "general") -> tuple[int, int]:
        if fuente not in ("general", "sucursales"):
            raise ValueError(f"fuente debe ser 'general' o 'sucursales', no '{fuente}'")
        datos = parsear_stock_desde_xls(ruta)
        if fuente == "sucursales":
            self._datos_sucursales = datos
            self._items_sucursales = self._transformar_items(datos)
            self._enriched_sucursales = self._enriquecer_items(self._items_sucursales)
            self._fecha_sucursales = datetime.now(timezone.utc)
            self._guardar_cache(settings.cache_ruta2, "sucursales")
        else:
            self._datos_general = datos
            self._items_general = self._transformar_items(datos)
            self._enriched_general = self._enriquecer_items(self._items_general)
            self._fecha_general = datetime.now(timezone.utc)
            self._guardar_cache(settings.cache_ruta, "general")
        self._rebuild_todas()
        codigos = self._obtener_codigos_almacen(datos)
        return len(self._obtener_enriched_segun_fuente(fuente)), len(codigos)

    def listar_almacenes(self, tipo: Optional[str] = None) -> list[dict]:
        self._refrescar_si_es_necesario("general")
        self._refrescar_si_es_necesario("sucursales")
        almacenes_vistos: dict[str, int] = {}
        for item in self._items_general:
            for alm in item.almacenes:
                almacenes_vistos[alm.almacen] = (
                    almacenes_vistos.get(alm.almacen, 0) + 1
                )
        for item in self._items_sucursales:
            for alm in item.almacenes:
                almacenes_vistos[alm.almacen] = (
                    almacenes_vistos.get(alm.almacen, 0) + 1
                )
        resultado = sorted(
            [{"almacen": k, "total_skus": v, "tipo": _tipo_almacen(k)} for k, v in almacenes_vistos.items()],
            key=lambda x: (0 if x["almacen"] == ALMACEN_PRINCIPAL else 1, x["almacen"]),
        )
        if tipo and tipo != "todas":
            resultado = [a for a in resultado if a["tipo"] == tipo]
        return resultado

    def listar_lineas(self) -> list[dict]:
        self._refrescar_si_es_necesario("general")
        lineas_vistas: dict[str, int] = {}
        for item in self._items_general:
            if item.linea:
                lineas_vistas[item.linea] = lineas_vistas.get(item.linea, 0) + 1
        return sorted(
            [{"linea": k, "total_skus": v} for k, v in lineas_vistas.items()],
            key=lambda x: x["linea"],
        )

    def listar_categorias(self) -> list[dict]:
        self._refrescar_si_es_necesario("general")
        cats: dict[str, dict] = {}
        for item in self._items_general:
            cat = item.categoria or "SIN CATEGORIA"
            if cat not in cats:
                cats[cat] = {"categoria": cat, "total_skus": 0, "lineas": set()}
            cats[cat]["total_skus"] += 1
            if item.linea:
                cats[cat]["lineas"].add(item.linea)
        return sorted(
            [
                {"categoria": v["categoria"], "total_skus": v["total_skus"], "lineas": sorted(v["lineas"])}
                for v in cats.values()
            ],
            key=lambda x: x["categoria"],
        )

    # ── Metodos internos ────────────────────────────────────────────────

    def _enriquecer_todo(self) -> None:
        """Re-enriquece todas las fuentes y reconstruye el merge."""
        self._enriched_general = self._enriquecer_items(self._items_general)
        self._enriched_sucursales = self._enriquecer_items(self._items_sucursales)
        self._rebuild_todas()

    def _rebuild_todas(self) -> None:
        """Reconstruye el merge de enriched_general + enriched_sucursales."""
        self._enriched_todas = self._merge_items_por_sku(
            self._enriched_general, self._enriched_sucursales,
        )

    @staticmethod
    def _es_momento_valido() -> bool:
        """Verifica si es horario laboral en Lima para descargar datos.

        Horario: Lunes a Sabado, 7:00 a 22:59 hora de Lima (-05:00).
        Domingos y fuera de horario se sirve cache vencido en vez de descargar.
        """
        ahora = datetime.now(LIMA_TZ)
        if ahora.weekday() == 6:  # domingo
            return False
        return 7 <= ahora.hour < 23  # 7:00 a 22:59

    def _obtener_enriched_segun_fuente(self, fuente: str) -> list[ItemStockEnriched]:
        if fuente == "sucursales":
            return self._enriched_sucursales
        if fuente == "todas":
            return self._enriched_todas
        return self._enriched_general

    def _enriquecer_items(self, items: list[ItemStock]) -> list[ItemStockEnriched]:
        """Merge stock items with catalog data."""
        sku_index: dict[str, int] = {}
        for i, sku in enumerate(catalog_service._catalog):
            sku_index[sku] = i

        enriched = []
        for item in items:
            cat = catalog_service.buscar(item.sku)

            linea_id = _extraer_linea_id(item.linea)
            if not linea_id and cat:
                linea_id = item.sku[:2]

            if cat:
                cat_linea = cat.get("linea", "").strip()
                cat_grupo = cat.get("grupo", "").strip()
                cat_tipo = cat.get("tipo", "").strip()
                cat_familia = cat.get("familia", "").strip()
                cat_categoria = cat.get("categoria", "").strip()

                display_linea = item.linea if item.linea not in _PLACEHOLDERS else ""
                display_grupo = item.grupo if item.grupo not in _PLACEHOLDERS else ""
                display_tipo = item.tipo if item.tipo not in _PLACEHOLDERS else ""
                display_familia = item.familia if item.familia not in _PLACEHOLDERS else ""
                display_categoria = item.categoria if item.categoria not in _PLACEHOLDERS else ""
                if display_linea and " - " not in display_linea and cat_linea:
                    display_linea = f"{display_linea} - {cat_linea}"
                display_grupo = display_grupo or cat_grupo
                display_tipo = display_tipo or cat_tipo
                display_familia = display_familia or cat_familia
                display_categoria = display_categoria or cat_categoria

                enriched.append(ItemStockEnriched(
                    sku=item.sku,
                    descripcion=item.descripcion,
                    um=item.um,
                    linea=display_linea,
                    grupo=display_grupo,
                    tipo=display_tipo,
                    familia=display_familia,
                    categoria=display_categoria,
                    un_bx=cat.get("un_bx", 1),
                    peso_kg=cat.get("peso_kg", 0.0),
                    precio=cat.get("precio", 0.0),
                    nombre_corto=cat.get("nombre_corto", ""),
                    ean13=cat.get("ean13", ""),
                    ean14=cat.get("ean14", ""),
                    estado_linea=cat.get("estado_linea", ""),
                    keywords=cat.get("keywords", []),
                    orden=cat.get("orden", sku_index.get(item.sku, 0)),
                    linea_id=linea_id,
                    sin_catalogo=False,
                    almacenes=item.almacenes,
                ))
            else:
                display_linea = item.linea or (f"{linea_id} - UNKNOWN" if linea_id else "")
                enriched.append(ItemStockEnriched(
                    sku=item.sku,
                    descripcion=item.descripcion,
                    um=item.um,
                    linea=display_linea,
                    grupo=item.grupo,
                    tipo=item.tipo,
                    familia=item.familia,
                    categoria=item.categoria,
                    un_bx=1,
                    peso_kg=0.0,
                    precio=0.0,
                    nombre_corto="",
                    ean13="",
                    ean14="",
                    keywords=[],
                    orden=0,
                    linea_id=linea_id,
                    sin_catalogo=True,
                    almacenes=item.almacenes,
                ))
        return enriched

    @staticmethod
    def _merge_items_por_sku(
        items_a: list[ItemStockEnriched], items_b: list[ItemStockEnriched],
    ) -> list[ItemStockEnriched]:
        """Mergea dos listas de items por SKU, combinando los almacenes de ambos.
        Crea copias de los items para evitar mutar los originales."""
        import copy

        mapa: dict[str, ItemStockEnriched] = {}
        for item in items_a:
            mapa[item.sku] = item.model_copy(deep=True)
        for item in items_b:
            if item.sku in mapa:
                existentes = {a.almacen for a in mapa[item.sku].almacenes}
                for alm in item.almacenes:
                    if alm.almacen not in existentes:
                        mapa[item.sku].almacenes.append(alm.model_copy())
                mapa[item.sku].almacenes.sort(
                    key=lambda a: (0 if a.almacen == ALMACEN_PRINCIPAL else 1, a.almacen)
                )
            else:
                mapa[item.sku] = item.model_copy(deep=True)
        return sorted(mapa.values(), key=lambda x: x.sku)

    def _refrescar_si_es_necesario(self, fuente: str) -> None:
        """Decide si descargar datos frescos o servir el cache.

        Reglas:
        1. Sin cache → descarga forzada (sin importar dia/hora).
           Nunca responder mudo: es preferible datos viejos que nada.
        2. Cache vigente (< TTL) → sirve directo.
        3. Cache vencido + horario laboral (L-S 7:00-22:59 Lima) → descarga fresh.
        4. Cache vencido + fuera de horario / domingo → sirve cache vencido.
           El campo metadata.cache_expirado=True avisa al consumidor.
        5. Circuit breaker abierto → sirve cache sin intentar descargar.
        """
        ahora = datetime.now(timezone.utc)
        chequear = []
        if fuente in ("general", "todas"):
            chequear.append("general")
        if fuente in ("sucursales", "todas"):
            chequear.append("sucursales")
        for f in chequear:
            if f == "general":
                fecha = self._fecha_general
                hay_cache = bool(self._items_general)
                cb_abierto = self._cb_abierto_general
            else:
                fecha = self._fecha_sucursales
                hay_cache = bool(self._items_sucursales)
                cb_abierto = self._cb_abierto_sucursales

            if not hay_cache:
                # Sin datos: descarga forzada sin importar horario.
                # Es preferible un error que responder vacio.
                self._actualizar_desde_origen(f)
                continue

            # Circuit breaker: si esta abierto, no intentar descargar
            if cb_abierto and ahora < cb_abierto:
                logger.warning("Circuit breaker abierto para %s hasta %s", f, cb_abierto.isoformat())
                continue
            # Si el circuit breaker expiro, cerrarlo y permitir intento
            if cb_abierto and ahora >= cb_abierto:
                logger.info("Circuit breaker reseteado para %s", f)
                if f == "general":
                    self._cb_abierto_general = None
                    self._cb_fallos_general = 0
                else:
                    self._cb_abierto_sucursales = None
                    self._cb_fallos_sucursales = 0

            if not fecha:
                edad = timedelta.max
            else:
                edad = ahora - fecha

            if edad > timedelta(seconds=settings.cache_ttl_segundos) and self._es_momento_valido():
                self._actualizar_desde_origen(f)

    def _actualizar_desde_origen(self, fuente: str) -> None:
        url = settings.source2_url if fuente == "sucursales" else settings.source1_url
        cache_ruta = settings.cache_ruta2 if fuente == "sucursales" else settings.cache_ruta
        with self._lock:
            if fuente == "sucursales":
                fecha = self._fecha_sucursales
                hay_items = bool(self._items_sucursales)
            else:
                fecha = self._fecha_general
                hay_items = bool(self._items_general)
            # Si otro hilo ya actualizo mientras esperamos el lock, salir
            if fecha and datetime.now(timezone.utc) - fecha < timedelta(seconds=settings.cache_ttl_segundos):
                return
            try:
                ruta = self._descargar_xls(url)
                datos = parsear_stock_desde_xls(ruta)
                items = self._transformar_items(datos)
                enriched = self._enriquecer_items(items)
                ahora = datetime.now(timezone.utc)
                if fuente == "sucursales":
                    self._datos_sucursales = datos
                    self._items_sucursales = items
                    self._enriched_sucursales = enriched
                    self._fecha_sucursales = ahora
                    self._cb_fallos_sucursales = 0
                    self._cb_abierto_sucursales = None
                else:
                    self._datos_general = datos
                    self._items_general = items
                    self._enriched_general = enriched
                    self._fecha_general = ahora
                    self._cb_fallos_general = 0
                    self._cb_abierto_general = None
                self._rebuild_todas()
                self._guardar_cache(cache_ruta, fuente)
                Path(ruta).unlink(missing_ok=True)
                logger.info("Cache %s actualizado: %d SKUs", fuente, len(items))
            except Exception:
                # Actualizar circuit breaker
                if fuente == "sucursales":
                    self._cb_fallos_sucursales += 1
                    if self._cb_fallos_sucursales >= settings.circuit_breaker_max_fallos:
                        self._cb_abierto_sucursales = datetime.now(timezone.utc) + timedelta(seconds=settings.circuit_breaker_reset_seg)
                        logger.error("Circuit breaker ABIERTO para sucursales por %ds (fallos: %d)",
                                     settings.circuit_breaker_reset_seg, self._cb_fallos_sucursales)
                else:
                    self._cb_fallos_general += 1
                    if self._cb_fallos_general >= settings.circuit_breaker_max_fallos:
                        self._cb_abierto_general = datetime.now(timezone.utc) + timedelta(seconds=settings.circuit_breaker_reset_seg)
                        logger.error("Circuit breaker ABIERTO para general por %ds (fallos: %d)",
                                     settings.circuit_breaker_reset_seg, self._cb_fallos_general)
                logger.exception("Error actualizando cache %s", fuente)
                if not hay_items:
                    raise RuntimeError(
                        f"No hay datos en cache y la descarga desde appweb fallo (fuente={fuente})."
                    ) from None

    def _descargar_xls(self, url: str) -> str:
        for intento in range(2):
            try:
                respuesta = httpx.get(
                    url,
                    headers=ENCABEZADOS_HTTP,
                    timeout=30,
                    follow_redirects=True,
                )
                respuesta.raise_for_status()
                # Limitar tamano de descarga
                content_length = len(respuesta.content)
                if content_length > settings.xls_max_bytes:
                    raise RuntimeError(
                        f"XLS demasiado grande: {content_length} bytes (max: {settings.xls_max_bytes})"
                    )
                break
            except (httpx.TimeoutException, httpx.NetworkError) as e:
                if intento == 1:
                    raise  # reintentado una vez, fallo de nuevo
                continue
        sufijo = self._inferir_extension(respuesta)
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=sufijo)
        tmp.write(respuesta.content)
        ruta = tmp.name
        tmp.close()
        return ruta

    @staticmethod
    def _inferir_extension(respuesta: httpx.Response) -> str:
        ct = (respuesta.headers.get("content-type") or "").lower()
        if "spreadsheetml" in ct or "openxmlformats" in ct:
            return ".xlsx"
        if "excel" in ct:
            return ".xls"
        cd = respuesta.headers.get("content-disposition") or ""
        if ".xlsx" in cd:
            return ".xlsx"
        if ".xls" in cd:
            return ".xls"
        return ".xls"

    @staticmethod
    def _transformar_items(
        datos: dict[str, dict[str, dict]],
    ) -> list[ItemStock]:
        skus_unicos: dict[str, dict] = {}
        for almacen, productos in datos.items():
            tipo_alm = _tipo_almacen(almacen)
            for sku, info in productos.items():
                if sku not in skus_unicos:
                    linea_txt = info.get("linea", "")
                    linea_norm = _normalizar_linea(linea_txt)
                    skus_unicos[sku] = {
                        "descripcion": info.get("descripcion", ""),
                        "um": info.get("um", ""),
                        "linea": linea_norm,
                        "linea_id": _extraer_linea_id(linea_norm),
                        "grupo": info.get("grupo", ""),
                        "tipo": info.get("tipo", ""),
                        "familia": info.get("familia", ""),
                        "categoria": asignar_categoria(linea_norm),
                        "almacenes": {},
                    }
                skus_unicos[sku]["almacenes"][almacen] = {
                    "stock": info.get("stock", 0) or 0,
                    "predespacho": info.get("predespacho", 0) or 0,
                    "tipo": tipo_alm,
                }
        items = []
        for sku, data in sorted(skus_unicos.items()):
            almacenes_lista = [
                AlmacenStock(
                    almacen=alm,
                    tipo=val["tipo"],
                    stock=val["stock"],
                    predespacho=val["predespacho"],
                    disponible=max(0, val["stock"] - val["predespacho"]),
                )
                for alm, val in sorted(
                    data["almacenes"].items(),
                    key=lambda x: (0 if x[0] == ALMACEN_PRINCIPAL else 1, x[0]),
                )
            ]
            items.append(
                ItemStock(
                    sku=sku,
                    descripcion=data["descripcion"],
                    um=data["um"],
                    linea=data["linea"],
                    grupo=data["grupo"],
                    tipo=data["tipo"],
                    familia=data["familia"],
                    categoria=data["categoria"],
                    almacenes=almacenes_lista,
                    estado_linea="",
                    linea_id=data["linea_id"],
                    sin_catalogo=False,
                )
            )
        return items

    def _construir_respuesta(
        self,
        items: list[ItemStockEnriched],
        fuente: str = "general",
        almacen: Optional[str] = None,
        busqueda: Optional[str] = None,
        linea: Optional[str] = None,
        grupo: Optional[str] = None,
        um: Optional[str] = None,
        categoria: Optional[str] = None,
        limit: Optional[int] = None,
        offset: int = 0,
        tipo: Optional[str] = None,
    ) -> StockEnrichedResponse:
        if almacen:
            almacen_up = almacen.strip().upper()
            items = [
                item
                for item in items
                if any(a.almacen == almacen_up for a in item.almacenes)
            ]
        if busqueda:
            q = busqueda.strip().lower()
            items = [
                item
                for item in items
                if q in item.sku.lower() or q in item.descripcion.lower()
            ]
        if linea:
            q = linea.strip().lower()
            items = [item for item in items if q in item.linea.lower()]
        if grupo:
            q = grupo.strip().lower()
            items = [item for item in items if q in item.grupo.lower()]
        if um:
            q = um.strip().upper()
            items = [item for item in items if item.um == q]
        if categoria:
            q = categoria.strip().upper()
            items = [item for item in items if item.categoria == q]
        if tipo:
            tipo_lower = tipo.strip().lower()
            items = [
                item
                for item in items
                if any(a.tipo == tipo_lower for a in item.almacenes)
            ]

        total = len(items)
        if limit is not None:
            items = items[offset:offset + limit]

        fuente_label = {
            "general": "General (VES, 40, 118...)",
            "sucursales": "Sucursales (S1, S2, S3...)",
            "todas": "General + Sucursales",
        }.get(fuente, fuente)

        ahora = datetime.now(timezone.utc)

        # Determinar fecha de referencia y total_almacenes segun fuente
        if fuente == "sucursales":
            ref_fecha = self._fecha_sucursales
            datos_ref = self._datos_sucursales
        elif fuente == "todas":
            # Tomar la mas reciente de ambas fuentes
            ref_fecha = self._fecha_general
            if self._fecha_sucursales and (not ref_fecha or self._fecha_sucursales > ref_fecha):
                ref_fecha = self._fecha_sucursales
            datos_ref = {}
            datos_ref.update(self._datos_general)
            datos_ref.update(self._datos_sucursales)
        else:
            ref_fecha = self._fecha_general
            datos_ref = self._datos_general

        cache_expirado = bool(ref_fecha and ahora - ref_fecha > timedelta(seconds=settings.cache_ttl_segundos))

        return StockEnrichedResponse(
            metadata=MetadataStock(
                fuente=fuente_label,
                fecha_descarga=_a_lima(ref_fecha),
                total_skus=total,
                total_almacenes=len(self._obtener_codigos_almacen(datos_ref)),
                cache_expirado=cache_expirado,
                cache_expiro_en=settings.cache_ttl_segundos,
                offset=offset,
                limit=limit,
                enriquecido=catalog_service.cargado,
            ),
            items=list(items),
        )

    def _calcular_resumen(self) -> ResumenStock:
        total = len(self._items_general)
        con_stock = 0
        sin_stock = 0
        con_predespacho = 0
        for item in self._items_general:
            tiene_disponible = any(a.disponible > 0 for a in item.almacenes)
            tiene_predespacho = any(a.predespacho > 0 for a in item.almacenes)
            if tiene_disponible:
                con_stock += 1
            else:
                sin_stock += 1
            if tiene_predespacho:
                con_predespacho += 1
        almacenes = self.listar_almacenes()
        return ResumenStock(
            total_skus=total,
            total_almacenes=len(almacenes),
            skus_con_stock=con_stock,
            skus_sin_stock=sin_stock,
            skus_con_predespacho=con_predespacho,
            almacenes=almacenes,
        )

    @staticmethod
    def _obtener_codigos_almacen(datos: dict[str, dict[str, dict]]) -> list[str]:
        return sorted(datos.keys())

    def _guardar_cache(self, ruta_cache: str, fuente: str) -> None:
        ruta = Path(ruta_cache)
        ruta_bak = ruta.with_suffix(ruta.suffix + ".bak")
        try:
            ruta.parent.mkdir(parents=True, exist_ok=True)
            datos = self._datos_sucursales if fuente == "sucursales" else self._datos_general
            fecha = self._fecha_sucursales if fuente == "sucursales" else self._fecha_general
            payload = {
                "fecha_descarga": fecha.isoformat() if fecha else None,
                "datos": datos,
            }
            ruta.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            shutil.copy2(str(ruta), str(ruta_bak))
        except OSError:
            logger.exception("Error guardando cache %s en %s", fuente, ruta_cache)

    def _cargar_cache(self, ruta_cache: str, fuente: str) -> None:
        for ruta in (Path(ruta_cache), Path(ruta_cache).with_suffix(Path(ruta_cache).suffix + ".bak")):
            if not ruta.exists():
                continue
            try:
                payload = json.loads(ruta.read_text(encoding="utf-8"))
                fecha_str = payload.get("fecha_descarga")
                datos = payload.get("datos", {})
                items = self._transformar_items(datos)
                if fuente == "sucursales":
                    if fecha_str:
                        self._fecha_sucursales = datetime.fromisoformat(fecha_str)
                        if self._fecha_sucursales.tzinfo is None:
                            self._fecha_sucursales = self._fecha_sucursales.replace(tzinfo=timezone.utc)
                    self._datos_sucursales = datos
                    self._items_sucursales = items
                else:
                    if fecha_str:
                        self._fecha_general = datetime.fromisoformat(fecha_str)
                        if self._fecha_general.tzinfo is None:
                            self._fecha_general = self._fecha_general.replace(tzinfo=timezone.utc)
                    self._datos_general = datos
                    self._items_general = items
                logger.info("Cache %s cargado desde %s: %d SKUs", fuente, ruta, len(items))
                return  # exito
            except (OSError, json.JSONDecodeError, ValueError) as e:
                logger.warning("Error cargando cache %s desde %s: %s", fuente, ruta, e)
                continue  # intenta backup


servicio_stock = ServicioStock()
