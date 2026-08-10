from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.models.schemas import ItemStockEnriched, StockEnrichedResponse
from app.services.s1_service import servicio_stock

router = APIRouter(tags=["stock"])


@router.get(
    "/api/v1/stock",
    response_model=StockEnrichedResponse,
    summary="Listar stock de todos los productos",
    description="Obtiene el stock consolidado desde la fuente S1 (appweb.cipsa.com.pe). "
                "Acepta filtros opcionales, paginacion y categorizacion. "
                "Siempre devuelve datos enriquecidos con catalogo maestro (orden, un_bx, precio, ean, etc.).",
)
def listar_stock(
    almacen: Optional[str] = Query(None, description="Filtrar por codigo de almacen (ej: VES, 40, 118)"),
    search: Optional[str] = Query(None, description="Buscar por SKU o descripcion del producto"),
    linea: Optional[str] = Query(None, description="Filtrar por linea de producto (ej: PELOTAS, FORROS)"),
    grupo: Optional[str] = Query(None, description="Filtrar por grupo de producto (ej: NACIONAL, FOLDER)"),
    um: Optional[str] = Query(None, description="Filtrar por unidad de medida (ej: UND, BST, KGR, CJA)"),
    categoria: Optional[str] = Query(None, description="Filtrar por categoria de negocio (ej: VINIBALL, VINIFAN)"),
    tipo: Optional[str] = Query(None, description="Filtrar por tipo de almacen: venta, mktd"),
    fuente: str = Query("general", description="Fuente de datos: general, sucursales, todas"),
    limit: Optional[int] = Query(None, description="Maximo de items (paginacion). Ej: 100", ge=1, le=5000),
    offset: int = Query(0, description="Items a saltar (paginacion). Ej: 100", ge=0),
):
    return servicio_stock.obtener_stock(
        almacen=almacen, busqueda=search, linea=linea, grupo=grupo, um=um,
        categoria=categoria, tipo=tipo, fuente=fuente, limit=limit, offset=offset,
    )


@router.get(
    "/api/v1/stock/{sku}",
    response_model=ItemStockEnriched,
    summary="Obtener detalle de un SKU",
    description="Busca un producto por su codigo SKU y devuelve su detalle "
    "con desglose por almacen y datos enriquecidos del catalogo maestro.",
)
def obtener_sku(
    sku: str,
    fuente: str = Query(
        "general",
        description="Fuente de datos: general, sucursales, todas",
    ),
) -> ItemStockEnriched:
    item = servicio_stock.obtener_sku_enriched(sku.strip().upper(), fuente=fuente)
    if not item:
        raise HTTPException(
            status_code=404,
            detail=f"SKU '{sku}' no encontrado en el reporte de stock.",
        )
    return item


@router.get(
    "/api/v1/almacenes",
    summary="Listar almacenes disponibles",
    description="Devuelve la lista de codigos de almacen con la cantidad "
    "de SKU que tienen stock registrado en cada uno. Opcionalmente filtra por tipo: venta, mktd o todas.",
)
def listar_almacenes(tipo: Optional[str] = Query(None, description="Filtrar por tipo: venta, mktd, todas")):
    return servicio_stock.listar_almacenes(tipo=tipo)


@router.get(
    "/api/v1/lineas",
    summary="Listar lineas de producto disponibles",
    description="Devuelve la lista de lineas de producto con la cantidad "
    "de SKU registrados en cada una (solamente disponible en formato completo).",
)
def listar_lineas():
    return servicio_stock.listar_lineas()


@router.get(
    "/api/v1/categorias",
    summary="Listar categorias de negocio",
    description="Devuelve la lista de categorias de negocio con las lineas "
    "que las componen y la cantidad de SKU en cada una.",
)
def listar_categorias():
    return servicio_stock.listar_categorias()
