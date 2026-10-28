from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field


class AlmacenStock(BaseModel):
    almacen: str = Field(..., description="Codigo del almacen")
    nombre: str = Field(default="", description="Nombre descriptivo del almacen")
    tipo: str = Field(default="venta", description="Tipo de almacen: venta, mktd")
    disponible: int = Field(
        ..., ge=0, description="Stock disponible (stock - predespacho)"
    )
    stock: int = Field(..., ge=0, description="Stock fisico en almacen")
    predespacho: int = Field(
        ..., ge=0, description="Unidades predespachadas/comprometidas"
    )


class ItemStock(BaseModel):
    sku: str = Field(..., description="Codigo unico del producto")
    descripcion: str = Field(
        default="", description="Nombre o descripcion del producto"
    )
    um: str = Field(default="", description="Unidad de medida (UND, BST, KGR, etc.)")
    um_nombre: str = Field(
        default="", description="Nombre descriptivo de unidad de medida"
    )
    linea: str = Field(
        default="", description="Linea de producto (formato: '01 - PELOTAS')"
    )
    linea_id: Optional[str] = Field(
        None, description="Short line identifier (e.g. '01', 'AD', '78')"
    )
    grupo: str = Field(default="", description="Grupo de producto")
    grupo_id: Optional[str] = Field(None, description="Short group identifier")
    tipo: str = Field(default="", description="Tipo de producto")
    tipo_id: Optional[str] = Field(None, description="Short type identifier")
    familia: str = Field(default="", description="Familia de producto")
    familia_id: Optional[str] = Field(None, description="Short family identifier")
    categoria: str = Field(
        default="",
        description="Categoria de negocio (VINIBALL, VINIFAN, REPRESENTADAS)",
    )
    almacenes: list[AlmacenStock] = Field(default_factory=list)
    estado_linea: str = Field(
        default="", description="Estado de linea (NACIONAL, IMPORTADO, NUEVO)"
    )
    sin_catalogo: bool = Field(
        False, description="True si el producto no tiene datos de catalogo maestro"
    )


class ItemStockEnriched(ItemStock):
    un_bx: int = Field(1, description="Unidades por caja")
    peso_kg: float = Field(0.0, description="Peso en kg")
    precio: float = Field(0.0, description="Precio de lista")
    nombre_corto: str = Field(default="", description="Nombre corto generado")
    ean13: str = Field(default="", description="Codigo de barras EAN-13")
    ean14: str = Field(default="", description="Codigo de envio EAN-14 (GS1)")
    keywords: list[str] = Field(
        default_factory=list, description="Keywords para busqueda"
    )
    orden: int = Field(0, description="Orden indice maestro del catalogo (SKU_BX)")
    sin_stock: bool = Field(
        False,
        description="True si el producto existe en catalogo pero no tiene stock en el reporte",
    )
    descontinuado: bool = Field(
        False,
        description="True si el ERP lo marca descontinuado (curado en SKU_BX para la venta)",
    )
    # ── Flags de negocio (v3.6.0 del catalogo) ─────────────────────────
    categoria_venta: str = Field(
        default="",
        description="Semaforo de venta: VINIBALL, VINIFAN, REPRESENTADAS o REVISION_VENTA",
    )
    en_guia: bool = Field(
        False, description="True si el SKU esta curado en la guia SKU_BX"
    )
    compromiso: bool = Field(
        False, description="True si tiene predespacho/compromiso de venta"
    )
    cotizable: bool = Field(
        False, description="True si tiene precio y se puede cotizar"
    )
    por_activar: bool = Field(
        False, description="True si esta en catalogo pero sin precio (falta activarlo)"
    )
    vigente: bool = Field(True, description="True si el ERP no lo marca descontinuado")
    origen: str = Field("", description="Fuente de la ficha comercial: 'erp' o 's1'")
    derivado_de: str = Field(
        "", description="SKU base cuando es un derivado por metodo D"
    )
    revision: str = Field(
        "",
        description=(
            "Estado que el frontend usa como badge: sin_catalogo, revision_venta, "
            "por_activar, descontinuado, compromiso o vacio (disponible)."
        ),
    )


class MetadataStock(BaseModel):
    fuente: str = Field(..., description="URL o nombre de la fuente de datos")
    fecha_descarga: Optional[datetime] = Field(
        None, description="Momento de la ultima descarga"
    )
    total_skus: int = Field(
        0, description="Cantidad total de SKU unicos (sin paginacion)"
    )
    total_almacenes: int = Field(0, description="Cantidad de almacenes")
    cache_expirado: bool = Field(False, description="Indica si se sirvio cache vencido")
    cache_expiro_en: int = Field(600, description="TTL del cache en segundos")
    offset: Optional[int] = Field(None, description="Offset aplicado en la paginacion")
    limit: Optional[int] = Field(None, description="Limite aplicado en la paginacion")
    enriquecido: bool = Field(
        False, description="Indica si se sirvio con datos del catalogo"
    )


class StockEnrichedResponse(BaseModel):
    metadata: MetadataStock
    items: list[ItemStockEnriched] = Field(
        default_factory=list, description="Lista de productos con stock + catalogo"
    )


class ItemStockCompact(BaseModel):
    """Item del reporte S1 sin desglose por almacen.

    Existe para que master-data (y cualquier consumidor que solo necesita el
    universo) no baje el JSON completo con almacenes: el reporte real tiene
    8 almacenes por SKU y el payload se multiplica por 8 sin aportar nada.
    """

    sku: str = Field(..., description="Codigo unico del producto")
    descripcion: str = Field(default="", description="Nombre o descripcion")
    um: str = Field(default="", description="Unidad de medida")
    um_nombre: str = Field(
        default="", description="Nombre descriptivo de unidad de medida"
    )
    linea: str = Field(
        default="", description="Linea con codigo y nombre (ej. '01 - PELOTAS')"
    )
    linea_id: Optional[str] = Field(
        None, description="Codigo corto de linea (ej. '01', 'CA')"
    )
    grupo: str = Field(default="", description="Grupo de producto")
    grupo_id: Optional[str] = Field(None, description="Codigo corto de grupo")
    tipo: str = Field(default="", description="Tipo de producto")
    tipo_id: Optional[str] = Field(None, description="Codigo corto de tipo")
    familia: str = Field(default="", description="Familia de producto")
    familia_id: Optional[str] = Field(None, description="Codigo corto de familia")
    categoria: str = Field(default="", description="Categoria de negocio")
    categoria_venta: str = Field(default="", description="Semaforo de venta")
    stock: int = Field(0, ge=0, description="Stock fisico total (suma de almacenes)")
    predespacho: int = Field(0, ge=0, description="Compromiso/predespacho total")
    disponible: int = Field(0, ge=0, description="Stock disponible total")
    sin_catalogo: bool = Field(
        False, description="True si no esta en el catalogo maestro"
    )


class MetadataStockCompact(BaseModel):
    fuente: str = Field(..., description="URL o nombre de la fuente de datos")
    fecha_descarga: Optional[datetime] = Field(
        None, description="Momento de la ultima descarga"
    )
    total_skus: int = Field(0, description="Cantidad total de SKU unicos")
    cache_expirado: bool = Field(False, description="Indica si se sirvio cache vencido")
    enriquecido: bool = Field(
        False, description="Indica si se sirvio con datos del catalogo"
    )


class StockCompactResponse(BaseModel):
    metadata: MetadataStockCompact
    items: list[ItemStockCompact] = Field(
        default_factory=list, description="Universo de stock consolidado por SKU"
    )


class ResumenStock(BaseModel):
    total_skus: int = Field(0, description="Total de SKU en el reporte")
    total_almacenes: int = Field(0, description="Cantidad de almacenes")
    skus_con_stock: int = Field(
        0, description="SKU con disponible > 0 en algun almacen"
    )
    skus_sin_stock: int = Field(
        0, description="SKU con disponible = 0 en todos los almacenes"
    )
    skus_con_predespacho: int = Field(
        0, description="SKU con predespacho > 0 en algun almacen"
    )
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
    total_almacenes: int = Field(0, description="Almacenes encontrados")


class CatalogUploadResponse(BaseModel):
    mensaje: str = Field(..., description="Resultado de la carga")
    total_skus: int = Field(0, description="SKU cargados en el catalogo")
    con_ean14: int = Field(0, description="SKU con EAN-14")
    con_unbx: int = Field(0, description="SKU con un_bx > 1")
    descontinuados: int = Field(0, description="SKU marcados descontinuados")


class CatalogHealthResponse(BaseModel):
    cargado: bool = Field(False, description="Si el catalogo esta cargado en memoria")
    total_skus: int = Field(0, description="Total de SKUs en el catalogo")
    edad_segundos: int = Field(0, description="Tiempo desde la ultima carga")
    stale: bool = Field(False, description="Si el catalogo ha excedido el TTL")
    ttl_segundos: int = Field(21600, description="TTL del catalogo en segundos")


class CatalogoEntry(BaseModel):
    sku: str = Field(..., description="Codigo unico del producto")
    nombre: str = Field(default="", description="Nombre o descripcion del producto")
    nombre_corto: str = Field(default="", description="Nombre corto generado")
    linea: str = Field(default="", description="Codigo de linea de producto (2 chars)")
    linea_nombre: str = Field(default="", description="Nombre legible de la linea")
    grupo: str = Field(default="", description="Grupo de producto")
    tipo: str = Field(default="", description="Tipo de producto")
    familia: str = Field(default="", description="Familia de producto")
    categoria: str = Field(default="", description="Categoria de negocio")
    estado_linea: str = Field(
        default="", description="Estado de linea (NACIONAL, IMPORTADO, NUEVO)"
    )
    un_bx: int = Field(1, description="Unidades por caja")
    peso_kg: float = Field(0.0, description="Peso en kg")
    precio: float = Field(0.0, description="Precio de lista")
    ean13: str = Field(default="", description="Codigo de barras EAN-13")
    ean14: str = Field(default="", description="Codigo de envio EAN-14 (GS1)")
    keywords: list[str] = Field(
        default_factory=list, description="Keywords para busqueda"
    )
    orden: int = Field(0, description="Orden indice maestro del catalogo")
    descontinuado: bool = Field(
        False,
        description="True si el ERP lo marca descontinuado (curado en SKU_BX para la venta)",
    )
    # ── Flags de negocio publicados por master-data (v3.6.0) ───────────
    categoria_venta: str = Field(
        default="",
        description="Semaforo de venta: VINIBALL, VINIFAN, REPRESENTADAS o REVISION_VENTA",
    )
    um: str = Field(default="", description="Unidad de medida (viene del reporte S1)")
    en_guia: bool = Field(
        False, description="True si el SKU esta curado en la guia SKU_BX"
    )
    compromiso: bool = Field(
        False, description="True si tenia predespacho al generar el catalogo"
    )
    cotizable: bool = Field(
        False, description="True si tiene precio y se puede cotizar"
    )
    por_activar: bool = Field(
        False, description="True si esta en catalogo pero sin precio"
    )
    vigente: bool = Field(True, description="True si el ERP no lo marca descontinuado")
    origen: str = Field("", description="Fuente de la ficha comercial: 'erp' o 's1'")
    derivado_de: str = Field(
        "", description="SKU base cuando es un derivado por metodo D"
    )
    stock_snapshot: int = Field(
        0, description="Stock del reporte S1 al generar el catalogo (solo trazabilidad)"
    )
    predespacho_snapshot: int = Field(
        0, description="Compromiso del reporte S1 al generar el catalogo (trazabilidad)"
    )


class CatalogoMetadata(BaseModel):
    cargado: bool = Field(False, description="Si el catalogo esta cargado en memoria")
    total_skus: int = Field(0, description="Total de SKUs en el catalogo")
    generated_at: Optional[datetime] = Field(
        None, description="Momento de la ultima carga del catalogo"
    )
    categorias_por_linea: dict[str, str] = Field(
        default_factory=dict,
        description=(
            "Taxonomia linea(codigo) -> categoria publicada por master-data. "
            "Fuente unica: evita que cada consumidor mantenga su propia copia."
        ),
    )
    lineas_nombre_a_codigo: dict[str, str] = Field(
        default_factory=dict,
        description="Mapa nombre de linea -> codigo, publicado por master-data",
    )


class CatalogoResponse(BaseModel):
    metadata: CatalogoMetadata
    items: list[CatalogoEntry] = Field(
        default_factory=list, description="Catalogo maestro completo sin stock"
    )
