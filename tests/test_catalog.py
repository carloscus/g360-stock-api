"""Tests para el endpoint de catalogo (upload + health)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.catalog_service import catalog_service

client = TestClient(app)
RUTA_CATALOGO = Path(__file__).parent.parent.parent / "g360-master-data" / "output" / "catalogo_productos.json"


class TestCatalogHealth:
    def test_health_sin_catalogo(self):
        """Health debe indicar que no hay catalogo cargado inicialmente."""
        # Asegurarse de que no hay catalogo cargado
        catalog_service._catalog = {}
        catalog_service._fecha_carga = None

        respuesta = client.get("/api/v1/catalog/health")
        assert respuesta.status_code == 200
        datos = respuesta.json()
        assert datos["cargado"] is False
        assert datos["total_skus"] == 0
        assert datos["stale"] is True

    def test_health_con_catalogo(self):
        """Health debe mostrar estado correcto cuando hay catalogo."""
        if not RUTA_CATALOGO.exists():
            pytest.skip("No hay archivo de catalogo para probar")

        with open(RUTA_CATALOGO, encoding="utf-8") as f:
            data = json.load(f)

        catalog_service.cargar_desde_json(data)

        respuesta = client.get("/api/v1/catalog/health")
        assert respuesta.status_code == 200
        datos = respuesta.json()
        assert datos["cargado"] is True
        assert datos["total_skus"] > 0
        assert datos["stale"] is False

        # Limpiar
        catalog_service._catalog = {}
        catalog_service._fecha_carga = None


class TestCatalogUpload:
    def test_upload_sin_archivo(self):
        respuesta = client.post("/api/v1/catalog/upload")
        assert respuesta.status_code == 422

    def test_upload_archivo_no_json(self):
        respuesta = client.post(
            "/api/v1/catalog/upload",
            files={"archivo": ("test.txt", b"hello", "text/plain")}
        )
        assert respuesta.status_code == 400
        assert "Formato no soportado" in respuesta.json()["detail"]

    @pytest.mark.skipif(not RUTA_CATALOGO.exists(), reason="No hay archivo de catalogo")
    def test_upload_catalogo_valido(self):
        with open(RUTA_CATALOGO, encoding="utf-8") as f:
            contenido = f.read()

        respuesta = client.post(
            "/api/v1/catalog/upload",
            files={"archivo": ("catalogo_productos.json", contenido, "application/json")}
        )
        assert respuesta.status_code == 200
        datos = respuesta.json()
        assert datos["total_skus"] > 0
        assert datos["mensaje"] == "Catalogo cargado correctamente"

        # Verificar que el catalogo esta cargado
        assert catalog_service.cargado
        assert catalog_service.total_skus == datos["total_skus"]

        # Limpiar
        catalog_service._catalog = {}
        catalog_service._fecha_carga = None

    @pytest.mark.skipif(not RUTA_CATALOGO.exists(), reason="No hay archivo de catalogo")
    def test_stock_con_enrich(self):
        """Verificar que /stock?enrich=true retorna campos del catalogo."""
        # Cargar catalogo
        with open(RUTA_CATALOGO, encoding="utf-8") as f:
            data = json.load(f)
        catalog_service.cargar_desde_json(data)

        # Cargar stock de prueba
        from app.services.s1_service import servicio_stock
        sample = Path(__file__).parent / "samples" / "REPT_STOCK_SAMPLE.xls"
        if sample.exists():
            servicio_stock.procesar_archivo_local(str(sample))

        respuesta = client.get("/api/v1/stock?enrich=true&limit=1")
        assert respuesta.status_code == 200
        datos = respuesta.json()
        assert datos["metadata"]["enriquecido"] is True
        assert len(datos["items"]) >= 1

        # Verificar que los items tienen campos enrich
        item = datos["items"][0]
        assert "un_bx" in item
        assert "precio" in item
        assert "ean13" in item
        assert "estado_linea" in item

        # Limpiar
        catalog_service._catalog = {}
        catalog_service._fecha_carga = None

    @pytest.mark.skipif(not RUTA_CATALOGO.exists(), reason="No hay archivo de catalogo")
    def test_sku_con_enrich(self):
        """Verificar que /stock/{sku}?enrich=true retorna campos del catalogo."""
        import json as _json
        with open(RUTA_CATALOGO, encoding="utf-8") as f:
            data = _json.load(f)
        catalog_service.cargar_desde_json(data)

        sku_ejemplo = data["productos"][0]["sku"]
        respuesta = client.get(f"/api/v1/stock/{sku_ejemplo}", params={"enrich": "true"})
        assert respuesta.status_code == 200
        item = respuesta.json()
        assert item["sku"] == sku_ejemplo
        assert "un_bx" in item
        assert "estado_linea" in item

        # Limpiar
        catalog_service._catalog = {}
        catalog_service._fecha_carga = None
