from __future__ import annotations

import json
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


LIMA_TZ = timezone(timedelta(hours=-5))


def _extraer_linea_id(linea: str) -> Optional[str]:
    """Extract short line ID from linea code.
    Works with: '0101' -> '01', '0101 - PELOTAS' -> '01',
    '01 - PELOTAS' -> '01', 'AD - ACCESORIOS' -> 'AD', '78' -> '78', 'MA' -> 'MA'
    """
    if not linea:
        return None
    # Plain 2-char code: '01', '78', 'MA', 'AD'
    match = re.match(r'^([0-9A-Z]{2})$', linea)
    if match:
        return match.group(1)
    # 4-digit plain code: '0101' -> '01'
    match = re.match(r'^01([0-9]{2})$', linea)
    if match:
        return match.group(1)
    # 4-char alphanum plain code: '01AD' -> 'AD'
    match = re.match(r'^01([0-9A-Z]+)$', linea)
    if match:
        suffix = match.group(1)
        if suffix and suffix[0].isdigit():
            return suffix[:2]
        return suffix
    # With name separator: '01 - PELOTAS', 'AD - ACCESORIOS', '0101 - PELOTAS'
    match = re.match(r'^01([0-9A-Z]+)\s*-', linea)
    if match:
        suffix = match.group(1)
        if suffix and suffix[0].isdigit():
            return suffix[:2]
        return suffix
    match = re.match(r'^([0-9A-Z]{2,4})\s*-', linea)
    if match:
        return match.group(1)
    return None


def _normalizar_linea(linea: str) -> str:
    """Normalize line format for display.
    Handles: '0101' -> '01', '0101 - PELOTAS' -> '01 - PELOTAS',
    '01AD - ACCESORIOS' -> 'AD - ACCESORIOS', '01 - PELOTAS' -> '01 - PELOTAS'
    """
    if not linea:
        return ""
    # Plain 4-digit code with no separator: '0101' -> '01'
    match = re.match(r'^01([0-9]{2})$', linea)
    if match:
        return match.group(1)
    # Plain 4-char alphanum code: '01AD' -> 'AD'
    match = re.match(r'^01([0-9A-Z]+)$', linea)
    if match:
        suffix = match.group(1)
        if suffix and suffix[0].isdigit():
            return suffix[:2]
        return suffix
    # Full code with name: '0101 - PELOTAS' or '01AD - ACCESORIOS'
    match = re.match(r'^01([0-9A-Z]+)\s*-\s*(.+)$', linea)
    if match:
        suffix = match.group(1)
        rest = match.group(2).strip()
        if suffix and suffix[0].isdigit():
            return f"{suffix[:2]} - {rest}"
        return f"{suffix} - {rest}"
    # Already normalized: '01 - PELOTAS' or 'AD - ACCESORIOS'
    if re.match(r'^[0-9A-Z]{2,4}\s*-', linea):
        return linea
    return linea


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
        self._fecha_general: Optional[datetime] = None
        # Fuente sucursales
        self._datos_sucursales: dict[str, dict[str, dict]] = {}
        self._items_sucursales: list[ItemStock] = []
        self._fecha_sucursales: Optional[datetime] = None

        self._cargar_cache(settings.cache_ruta, "general")
        self._cargar_cache(settings.cache_ruta2, "sucursales")

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
        self._refrescar_si_es_necesario(fuente)
        items = self._obtener_items_segun_fuente(fuente)
        items_enriched = self._enriquecer_items(items)
        return self._construir_respuesta(items_enriched, fuente, almacen, busqueda, linea, grupo, um, categoria, limit, offset, tipo=tipo)

    def obtener_sku_enriched(self, sku: str, fuente: str = "general") -> Optional[ItemStockEnriched]:
        self._refrescar_si_es_necesario(fuente)
        items = self._obtener_items_segun_fuente(fuente)
        items_enriched = self._enriquecer_items(items)
        for item in items_enriched:
            if item.sku == sku:
                return item
        return None

    def _enriquecer_items(self, items: list[ItemStock]) -> list[ItemStockEnriched]:
        """Merge stock items with catalog data."""
        # Build SKU→index map from catalogue for orden
        sku_index: dict[str, int] = {}
        # Build SKU→line_id map from catalogue (each product's SKU prefix IS its line ID)
        sku_linea_id: dict[str, str] = {}
        for i, (sku, product) in enumerate(catalog_service._catalog.items()):
            sku_index[sku] = i
            sku_linea_id[sku] = sku[:2]

        enriched = []
        for item in items:
            cat = catalog_service.buscar(item.sku)
            sin_catalogo = cat is None

            # Extract line ID: try item.linea first, then SKU prefix from catalogue
            linea_id = _extraer_linea_id(item.linea)
            if not linea_id and cat:
                linea_id = sku_linea_id.get(item.sku)

            if cat:
                # Build display linea from catalogue data
                cat_linea = cat.get("linea", "").strip()
                cat_grupo = cat.get("grupo", "").strip()
                cat_tipo = cat.get("tipo", "").strip()
                cat_familia = cat.get("familia", "").strip()
                cat_categoria = cat.get("categoria", "").strip()

                # XLS data takes priority; catalog fills only empty values or placeholders
                _PLACEHOLDERS = {"", "TODOS"}
                display_linea = item.linea if item.linea not in _PLACEHOLDERS else ""
                display_grupo = item.grupo if item.grupo not in _PLACEHOLDERS else ""
                display_tipo = item.tipo if item.tipo not in _PLACEHOLDERS else ""
                display_familia = item.familia if item.familia not in _PLACEHOLDERS else ""
                display_categoria = item.categoria if item.categoria not in _PLACEHOLDERS else ""
                # Build display linea: "01 - PELOTAS" only if XLS only has the ID
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

    def obtener_resumen(self) -> ResumenStock:
        self._refrescar_si_es_necesario("general")
        return self._calcular_resumen()

    def obtener_health(self) -> HealthResponse:
        ahora = datetime.now(timezone.utc)
        valido = bool(self._fecha_general and ahora - self._fecha_general <= timedelta(seconds=settings.cache_ttl_segundos))
        return HealthResponse(
            status="ok",
            timestamp=ahora,
            cache_skus=len(self._items_general),
            cache_valido=valido,
        )

    def procesar_archivo_local(self, ruta: str, fuente: str = "general") -> tuple[int, int]:
        datos = parsear_stock_desde_xls(ruta)
        if fuente == "sucursales":
            self._datos_sucursales = datos
            self._items_sucursales = self._transformar_items(datos)
            self._fecha_sucursales = datetime.now(timezone.utc)
            self._guardar_cache(settings.cache_ruta2, "sucursales")
        else:
            self._datos_general = datos
            self._items_general = self._transformar_items(datos)
            self._fecha_general = datetime.now(timezone.utc)
            self._guardar_cache(settings.cache_ruta, "general")
        codigos = self._obtener_codigos_almacen(datos)
        return len(self._obtener_items_segun_fuente(fuente)), len(codigos)

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

    @staticmethod
    def _es_momento_valido() -> bool:
        ahora = datetime.now(LIMA_TZ)
        if ahora.weekday() == 6:  # domingo
            return False
        return 7 <= ahora.hour < 23  # 7:00 a 22:59

    def _obtener_items_segun_fuente(self, fuente: str) -> list[ItemStock]:
        if fuente == "sucursales":
            return self._items_sucursales
        if fuente == "todas":
            return self._items_general + self._items_sucursales
        return self._items_general

    def _refrescar_si_es_necesario(self, fuente: str) -> None:
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
            else:
                fecha = self._fecha_sucursales
                hay_cache = bool(self._items_sucursales)

            if not hay_cache:
                self._actualizar_desde_origen(f)
                continue

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
            # Si otro hilo ya refresco mientras esperabamos el lock, salir
            if fecha and datetime.now(timezone.utc) - fecha < timedelta(seconds=settings.cache_ttl_segundos):
                return
            try:
                ruta = self._descargar_xls(url)
                datos = parsear_stock_desde_xls(ruta)
                items = self._transformar_items(datos)
                ahora = datetime.now(timezone.utc)
                if fuente == "sucursales":
                    self._datos_sucursales = datos
                    self._items_sucursales = items
                    self._fecha_sucursales = ahora
                else:
                    self._datos_general = datos
                    self._items_general = items
                    self._fecha_general = ahora
                self._guardar_cache(cache_ruta, fuente)
                Path(ruta).unlink(missing_ok=True)
            except Exception:
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
        ref_fecha = self._fecha_sucursales if fuente == "sucursales" else self._fecha_general
        cache_expirado = bool(ref_fecha and ahora - ref_fecha > timedelta(seconds=settings.cache_ttl_segundos))

        return StockEnrichedResponse(
            metadata=MetadataStock(
                fuente=fuente_label,
                fecha_descarga=ref_fecha,
                total_skus=total,
                total_almacenes=len(self._obtener_codigos_almacen(
                    self._datos_sucursales if fuente == "sucursales" else self._datos_general
                )),
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
            pass

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
                    self._datos_sucursales = datos
                    self._items_sucursales = items
                else:
                    if fecha_str:
                        self._fecha_general = datetime.fromisoformat(fecha_str)
                    self._datos_general = datos
                    self._items_general = items
                return  # exito
            except (OSError, json.JSONDecodeError, ValueError):
                continue  # intenta backup


servicio_stock = ServicioStock()
