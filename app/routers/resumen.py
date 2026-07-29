from __future__ import annotations

from fastapi import APIRouter

from app.models.schemas import ResumenStock
from app.services.s1_service import servicio_stock

router = APIRouter(tags=["resumen"])


@router.get(
    "/api/v1/resumen",
    response_model=ResumenStock,
    summary="Obtener resumen y KPIs del stock",
    description="Devuelve indicadores clave del reporte: total de SKU, "
    "productos con y sin stock, predespachados, y detalle por almacen.",
)
def obtener_resumen() -> ResumenStock:
    return servicio_stock.obtener_resumen()
