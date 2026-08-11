from __future__ import annotations

import json
from fastapi import APIRouter, HTTPException, UploadFile, File

from app.models.schemas import CatalogHealthResponse, CatalogUploadResponse
from app.services.catalog_service import catalog_service

router = APIRouter(tags=["catalog"])


@router.post(
    "/api/v1/catalog/upload",
    response_model=CatalogUploadResponse,
    summary="Subir catalogo de productos",
    description="Sube un archivo JSON generado por g360-master-data. "
                 "El catalogo se carga en memoria y se usa para enriquecer automaticamente "
                 "todas las respuestas de /api/v1/stock.",
)
async def subir_catalogo(archivo: UploadFile = File(..., description="catalogo_productos.json")) -> UploadResponse:
    nombre = (archivo.filename or "archivo").lower()
    if not nombre.endswith(".json"):
        raise HTTPException(status_code=400, detail="Formato no soportado. Solo se aceptan archivos .json")

    try:
        contenido = await archivo.read()
        data = json.loads(contenido.decode("utf-8"))
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=422, detail=f"JSON invalido: {e}")

    result = catalog_service.cargar_desde_json(data)
    return CatalogUploadResponse(
        mensaje="Catalogo cargado correctamente",
        total_skus=result["total_skus"],
        con_ean14=result["con_ean14"],
        con_unbx=result["con_unbx"],
    )


@router.get(
    "/api/v1/catalog/health",
    response_model=CatalogHealthResponse,
    summary="Estado del catalogo",
    description="Devuelve el estado del catalogo cargado en memoria.",
)
def estado_catalogo() -> CatalogHealthResponse:
    h = catalog_service.health()
    return CatalogHealthResponse(
        cargado=h["cargado"],
        total_skus=h["total_skus"],
        edad_segundos=h["edad_segundos"],
        stale=h["stale"],
        ttl_segundos=h["ttl_segundos"],
    )
