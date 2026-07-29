from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, HTTPException

from app.models.schemas import UploadResponse
from app.services.s1_service import servicio_stock

router = APIRouter(tags=["upload"])


@router.post(
    "/api/v1/upload",
    response_model=UploadResponse,
    summary="Subir archivo de stock manualmente",
    description="Permite subir un archivo XLS o XLSX con el reporte de stock "
    "desde appweb. Reemplaza el cache actual y lo sirve como fuente de datos. "
    "Util cuando el servicio no tiene acceso directo al origen S1.",
)
async def subir_archivo(
    archivo: UploadFile = File(..., description="Archivo .xls o .xlsx del reporte de stock"),
) -> UploadResponse:
    nombre = (archivo.filename or "archivo").lower()
    if not (nombre.endswith(".xls") or nombre.endswith(".xlsx")):
        raise HTTPException(
            status_code=400,
            detail="Formato no soportado. Solo se aceptan archivos .xls o .xlsx.",
        )
    try:
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=Path(nombre).suffix)
        contenido = await archivo.read()
        tmp.write(contenido)
        ruta_tmp = tmp.name
        tmp.close()
        total_skus, total_almacenes = servicio_stock.procesar_archivo_local(ruta_tmp)
        Path(ruta_tmp).unlink(missing_ok=True)
        return UploadResponse(
            mensaje="Archivo procesado correctamente. Cache actualizado.",
            total_skus=total_skus,
            total_almacenes=total_almacenes,
        )
    except Exception as e:
        raise HTTPException(
            status_code=422,
            detail=f"Error al procesar el archivo: {e}",
        )
