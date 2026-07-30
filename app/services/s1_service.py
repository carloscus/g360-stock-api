from __future__ import annotations

import json
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import httpx

from app.config import settings
from app.core.constants import ENCABEZADOS_HTTP, ALMACEN_PRINCIPAL, asignar_categoria
from app.core.parsers import parsear_stock_desde_xls
from app.models.schemas import (
    AlmacenStock,
    ItemStock,
    MetadataStock,
    StockResponse,
    ResumenStock,
    HealthResponse,
)


class ServicioStock:
    def __init__(self):
        self._datos_crudos: dict[str, dict[str, dict]] = {}
        self._items: list[ItemStock] = []
        self._fecha_descarga: Optional[datetime] = None
        self._cache_expirado: bool = False
        self._cargar_cache()

    # ── Metodos publicos ────────────────────────────────────────────────

    def obtener_stock(
        self,
        almacen: Optional[str] = None,
        busqueda: Optional[str] = None,
        linea: Optional[str] = None,
        um: Optional[str] = None,
        categoria: Optional[str] = None,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> StockResponse:
        if self._cache_expiro():
            self._actualizar_desde_origen()
        return self._construir_respuesta(almacen, busqueda, linea, um, categoria, limit, offset)

    def obtener_sku(self, sku: str) -> Optional[ItemStock]:
        if self._cache_expiro():
            self._actualizar_desde_origen()
        for item in self._items:
            if item.sku == sku:
                return item
        return None

    def obtener_resumen(self) -> ResumenStock:
        if self._cache_expiro():
            self._actualizar_desde_origen()
        return self._calcular_resumen()

    def obtener_health(self) -> HealthResponse:
        return HealthResponse(
            status="ok",
            timestamp=datetime.now(timezone.utc),
            cache_skus=len(self._items),
            cache_valido=not self._cache_expiro(),
        )

    def procesar_archivo_local(self, ruta: str) -> tuple[int, int]:
        datos = parsear_stock_desde_xls(ruta)
        self._datos_crudos = datos
        self._items = self._transformar_items(datos)
        self._fecha_descarga = datetime.now(timezone.utc)
        self._cache_expirado = False
        self._guardar_cache()
        almacenes = self._listar_almacenes(datos)
        return len(self._items), len(almacenes)

    def listar_almacenes(self) -> list[dict]:
        if self._cache_expiro():
            self._actualizar_desde_origen()
        almacenes_vistos: dict[str, int] = {}
        for item in self._items:
            for alm in item.almacenes:
                almacenes_vistos[alm.almacen] = (
                    almacenes_vistos.get(alm.almacen, 0) + 1
                )
        return sorted(
            [{"almacen": k, "total_skus": v} for k, v in almacenes_vistos.items()],
            key=lambda x: (0 if x["almacen"] == ALMACEN_PRINCIPAL else 1, x["almacen"]),
        )

    def listar_lineas(self) -> list[dict]:
        if self._cache_expiro():
            self._actualizar_desde_origen()
        lineas_vistas: dict[str, int] = {}
        for item in self._items:
            if item.linea:
                lineas_vistas[item.linea] = lineas_vistas.get(item.linea, 0) + 1
        return sorted(
            [{"linea": k, "total_skus": v} for k, v in lineas_vistas.items()],
            key=lambda x: x["linea"],
        )

    def listar_categorias(self) -> list[dict]:
        if self._cache_expiro():
            self._actualizar_desde_origen()
        cats: dict[str, dict] = {}
        for item in self._items:
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

    def _cache_expiro(self) -> bool:
        if not self._fecha_descarga:
            return True
        edad = datetime.now(timezone.utc) - self._fecha_descarga
        return edad > timedelta(seconds=settings.cache_ttl_segundos)

    def _actualizar_desde_origen(self) -> None:
        try:
            ruta = self._descargar_xls()
            datos = parsear_stock_desde_xls(ruta)
            self._datos_crudos = datos
            self._items = self._transformar_items(datos)
            self._fecha_descarga = datetime.now(timezone.utc)
            self._cache_expirado = False
            self._guardar_cache()
            Path(ruta).unlink(missing_ok=True)
        except Exception:
            if not self._items:
                raise RuntimeError(
                    "No hay datos en cache y la descarga desde appweb fallo."
                ) from None
            self._fecha_descarga = datetime.now(timezone.utc)
            self._cache_expirado = True

    def _descargar_xls(self) -> str:
        respuesta = httpx.get(
            settings.source1_url,
            headers=ENCABEZADOS_HTTP,
            timeout=60,
            follow_redirects=True,
        )
        respuesta.raise_for_status()
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
            for sku, info in productos.items():
                if sku not in skus_unicos:
                    linea_txt = info.get("linea", "")
                    skus_unicos[sku] = {
                        "descripcion": info.get("descripcion", ""),
                        "um": info.get("um", ""),
                        "linea": linea_txt,
                        "grupo": info.get("grupo", ""),
                        "tipo": info.get("tipo", ""),
                        "familia": info.get("familia", ""),
                        "categoria": asignar_categoria(linea_txt),
                        "almacenes": {},
                    }
                skus_unicos[sku]["almacenes"][almacen] = {
                    "stock": info.get("stock", 0) or 0,
                    "predespacho": info.get("predespacho", 0) or 0,
                }
        items = []
        for sku, data in sorted(skus_unicos.items()):
            almacenes_lista = [
                AlmacenStock(
                    almacen=alm,
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
                )
            )
        return items

    def _construir_respuesta(
        self,
        almacen: Optional[str] = None,
        busqueda: Optional[str] = None,
        linea: Optional[str] = None,
        um: Optional[str] = None,
        categoria: Optional[str] = None,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> StockResponse:
        items = self._items
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
        if um:
            q = um.strip().upper()
            items = [item for item in items if item.um == q]
        if categoria:
            q = categoria.strip().upper()
            items = [item for item in items if item.categoria == q]

        total = len(items)
        if limit is not None:
            items = items[offset:offset + limit]

        return StockResponse(
            metadata=MetadataStock(
                fuente=settings.source1_url,
                fecha_descarga=self._fecha_descarga,
                total_skus=total,
                total_almacenes=len(self._listar_almacenes(self._datos_crudos)),
                cache_expirado=self._cache_expirado,
                cache_expiro_en=settings.cache_ttl_segundos,
            ),
            items=items,
        )

    def _calcular_resumen(self) -> ResumenStock:
        total = len(self._items)
        con_stock = 0
        sin_stock = 0
        con_predespacho = 0
        for item in self._items:
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
    def _listar_almacenes(datos: dict[str, dict[str, dict]]) -> list[str]:
        return sorted(datos.keys())

    def _guardar_cache(self) -> None:
        try:
            ruta = Path(settings.cache_ruta)
            ruta.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "fecha_descarga": self._fecha_descarga.isoformat() if self._fecha_descarga else None,
                "datos": self._datos_crudos,
            }
            ruta.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError:
            pass

    def _cargar_cache(self) -> None:
        ruta = Path(settings.cache_ruta)
        if not ruta.exists():
            return
        try:
            payload = json.loads(ruta.read_text(encoding="utf-8"))
            fecha_str = payload.get("fecha_descarga")
            if fecha_str:
                self._fecha_descarga = datetime.fromisoformat(fecha_str)
            self._datos_crudos = payload.get("datos", {})
            self._items = self._transformar_items(self._datos_crudos)
        except (OSError, json.JSONDecodeError, ValueError):
            self._fecha_descarga = None
            self._datos_crudos = {}
            self._items = []


servicio_stock = ServicioStock()
