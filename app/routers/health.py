from __future__ import annotations

from fastapi import APIRouter

from app.models.schemas import HealthResponse
from app.services.s1_service import servicio_stock

router = APIRouter(tags=["health"])


@router.get(
    "/api/v1/health",
    response_model=HealthResponse,
    summary="Verificar estado del servicio",
    description="Devuelve el estado actual del servicio, incluyendo informacion del cache.",
)
def health_check() -> HealthResponse:
    return servicio_stock.obtener_health()
