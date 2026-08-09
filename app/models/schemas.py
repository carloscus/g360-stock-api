from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class AlmacenStock(BaseModel):
    almacen: str = Field(..., description="Codigo del almacen")
    tipo: str = Field(default="venta", description="Tipo de almacen: venta, informativo, sucursal")
    disponible: int = Field(..., ge=0, description="Stock disponible (stock - predespacho)")
    stock: int = Field(..., ge=0, description="Stock fisico en almacen")
    predespacho: int = Field(..., ge=0, description="Unidades predespachadas/comprometidas")


class ItemStock(BaseModel):
    sku: str = Field(..., description="Codigo unico del producto")
    descripcion: str = Field(default="", description="Nombre o descripcion del producto")
    um: str = Field(default="", description="Unidad de medida (UND, BST, KGR, etc.)")
    linea: str = Field(default="", description="Linea de producto")
    grupo: str = Field(default="", description="Grupo de producto")
    tipo: str = Field(default="", description="Tipo de producto")
    familia: str = Field(default="", description="Familia de producto")
    categoria: str = Field(default="", description="Categoria de negocio (VINIBALL, VINIFAN, REPRESENTADAS)")
    almacenes: list[AlmacenStock] = Field(default_factory=list)


class ItemStockEnriched(ItemStock):
    un_bx: int = Field(1, description="Unidades por caja")
    peso_kg: float = Field(0.0, description="Peso en kg")
    precio: float = Field(0.0, description="Precio de lista")
    nombre_corto: str = Field(default="", description="Nombre corto generado")
    ean13: str = Field(default="", description="Codigo de barras EAN-13")
    ean14: str = Field(default="", description="Codigo de envio EAN-14 (GS1)")
    estado_linea: str = Field(default="", description="Estado de linea (NACIONAL, IMPORTADO, NUEVO, TRADICIONAL)")
    keywords: list[str] = Field(default_factory=list, description="Keywords para busqueda")
    orden: int = Field(0, description="Orden indice maestro del catalogo (SKU_BX)")


class MetadataStock(BaseModel):
    fuente: str = Field(..., description="URL o nombre de la fuente de datos")
    fecha_descarga: Optional[datetime] = Field(None, description="Momento de la ultima descarga")
    total_skus: int = Field(0, description="Cantidad total de SKU unicos (sin paginacion)")
    total_almacenes: int = Field(0, description="Cantidad de almacenes")
    cache_expirado: bool = Field(False, description="Indica si se sirvio cache vencido")
    cache_expiro_en: int = Field(900, description="TTL del cache en segundos")
    offset: Optional[int] = Field(None, description="Offset aplicado en la paginacion")
    limit: Optional[int] = Field(None, description="Limite aplicado en la paginacion")
    enriquecido: bool = Field(False, description="Indica si se sirvio con datos del catalogo")


class StockResponse(BaseModel):
    metadata: MetadataStock
    items: list[ItemStock] = Field(default_factory=list, description="Lista de productos con stock")


class StockEnrichedResponse(BaseModel):
    metadata: MetadataStock
    items: list[ItemStockEnriched] = Field(default_factory=list, description="Lista de productos con stock + catalogo")


class ResumenStock(BaseModel):
    total_skus: int = Field(0, description="Total de SKU en el reporte")
    total_almacenes: int = Field(0, description="Cantidad de almacenes")
    skus_con_stock: int = Field(0, description="SKU con disponible > 0 en algun almacen")
    skus_sin_stock: int = Field(0, description="SKU con disponible = 0 en todos los almacenes")
    skus_con_predespacho: int = Field(0, description="SKU con predespacho > 0 en algun almacen")
    almacenes: list[dict] = Field(default_factory=list)


class HealthResponse(BaseModel):
    status: str = Field("ok", description="Estado del servicio")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Momento de la consulta",
    )
    cache_skus: int = Field(0, description="SKU en cache")
    cache_valido: bool = Field(False, description="Indica si el cache actual es valido")


class UploadResponse(BaseModel):
    mensaje: str = Field(..., description="Resultado de la carga")
    total_skus: int = Field(0, description="SKU procesados")
    con_ean14: int = Field(0, description="SKU con EAN-14")
    con_unbx: int = Field(0, description="SKU con un_bx > 1")


class CatalogHealthResponse(BaseModel):
    cargado: bool = Field(False, description="Si el catalogo esta cargado en memoria")
    total_skus: int = Field(0, description="Total de SKUs en el catalogo")
    edad_segundos: int = Field(0, description="Tiempo desde la ultima carga")
    stale: bool = Field(False, description="Si el catalogo ha excedido el TTL")
    ttl_segundos: int = Field(21600, description="TTL del catalogo en segundos")
