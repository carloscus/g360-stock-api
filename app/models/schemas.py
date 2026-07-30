from __future__ import annotations

from datetime import datetime, timezone
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
    linea: str = Field(default="", description="Linea de producto (solamente en formato completo)")
    grupo: str = Field(default="", description="Grupo de producto (solamente en formato completo)")
    tipo: str = Field(default="", description="Tipo de producto (solamente en formato completo)")
    familia: str = Field(default="", description="Familia de producto (solamente en formato completo)")
    categoria: str = Field(default="", description="Categoria de negocio (VINIBALL, VINIFAN, etc.)")
    almacenes: list[AlmacenStock] = Field(
        default_factory=list,
        description="Desglose de stock por almacen",
    )


class MetadataStock(BaseModel):
    fuente: str = Field(..., description="URL o nombre de la fuente de datos")
    fecha_descarga: Optional[datetime] = Field(None, description="Momento de la ultima descarga")
    total_skus: int = Field(0, description="Cantidad total de SKU unicos (sin paginacion)")
    total_almacenes: int = Field(0, description="Cantidad de almacenes")
    cache_expirado: bool = Field(False, description="Indica si se sirvio cache vencido")
    cache_expiro_en: int = Field(900, description="TTL del cache en segundos")
    offset: Optional[int] = Field(None, description="Offset aplicado en la paginacion")
    limit: Optional[int] = Field(None, description="Limite aplicado en la paginacion")


class StockResponse(BaseModel):
    metadata: MetadataStock
    items: list[ItemStock] = Field(default_factory=list, description="Lista de productos con stock")


class ResumenStock(BaseModel):
    total_skus: int = Field(0, description="Total de SKU en el reporte")
    total_almacenes: int = Field(0, description="Cantidad de almacenes")
    skus_con_stock: int = Field(0, description="SKU con disponible > 0 en algun almacen")
    skus_sin_stock: int = Field(0, description="SKU con disponible = 0 en todos los almacenes")
    skus_con_predespacho: int = Field(0, description="SKU con predespacho > 0 en algun almacen")
    almacenes: list[dict] = Field(
        default_factory=list,
        description="Lista de almacenes con su total de SKU",
    )


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
    total_almacenes: int = Field(0, description="Almacenes encontrados")
