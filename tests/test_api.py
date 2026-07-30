from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.s1_service import servicio_stock

RUTA_SAMPLE = Path(__file__).parent / "samples" / "REPT_STOCK_SAMPLE.xls"
client = TestClient(app)


def setup_module():
    if RUTA_SAMPLE.exists():
        servicio_stock.procesar_archivo_local(str(RUTA_SAMPLE))


@pytest.mark.skipif(not RUTA_SAMPLE.exists(), reason="No hay archivo sample")
class TestConSample:
    def test_health(self):
        respuesta = client.get("/api/v1/health")
        assert respuesta.status_code == 200
        datos = respuesta.json()
        assert datos["status"] == "ok"
        assert datos["cache_skus"] > 0

    def test_stock_lista(self):
        respuesta = client.get("/api/v1/stock")
        assert respuesta.status_code == 200
        datos = respuesta.json()
        assert datos["metadata"]["total_skus"] > 0
        assert len(datos["items"]) > 0

    def test_stock_por_sku(self):
        respuesta = client.get("/api/v1/stock")
        sku = respuesta.json()["items"][0]["sku"]
        detalle = client.get(f"/api/v1/stock/{sku}")
        assert detalle.status_code == 200
        assert detalle.json()["sku"] == sku

    def test_stock_sku_inexistente(self):
        respuesta = client.get("/api/v1/stock/ZZZZZZ99")
        assert respuesta.status_code == 404

    def test_stock_filtro_almacen(self):
        respuesta = client.get("/api/v1/stock?almacen=VES")
        assert respuesta.status_code == 200
        for item in respuesta.json()["items"]:
            almacenes = [a["almacen"] for a in item["almacenes"]]
            assert "VES" in almacenes

    def test_stock_busqueda(self):
        respuesta = client.get("/api/v1/stock?search=011019")
        assert respuesta.status_code == 200
        assert len(respuesta.json()["items"]) >= 1

    def test_stock_busqueda_por_descripcion(self):
        respuesta = client.get("/api/v1/stock?search=futbol")
        assert respuesta.status_code == 200
        assert len(respuesta.json()["items"]) >= 1

    def test_resumen(self):
        respuesta = client.get("/api/v1/resumen")
        assert respuesta.status_code == 200
        datos = respuesta.json()
        assert datos["total_skus"] > 0
        assert datos["total_almacenes"] >= 1
        assert datos["skus_con_stock"] + datos["skus_sin_stock"] == datos["total_skus"]

    def test_almacenes(self):
        respuesta = client.get("/api/v1/almacenes")
        assert respuesta.status_code == 200
        datos = respuesta.json()
        assert isinstance(datos, list)
        assert len(datos) >= 1
        assert "almacen" in datos[0]
        assert "total_skus" in datos[0]

    def test_upload_sin_archivo(self):
        respuesta = client.post("/api/v1/upload")
        assert respuesta.status_code == 422

    def test_disponible_nunca_negativo(self):
        respuesta = client.get("/api/v1/stock")
        for item in respuesta.json()["items"]:
            for alm in item["almacenes"]:
                assert alm["disponible"] >= 0, (
                    f"SKU {item['sku']} almacen {alm['almacen']}: "
                    f"disponible={alm['disponible']}"
                )

    def test_disponible_es_stock_menos_predespacho(self):
        respuesta = client.get("/api/v1/stock")
        for item in respuesta.json()["items"]:
            for alm in item["almacenes"]:
                esperado = max(0, alm["stock"] - alm["predespacho"])
                assert alm["disponible"] == esperado, (
                    f"SKU {item['sku']} almacen {alm['almacen']}: "
                    f"disp={alm['disponible']} != stock({alm['stock']}) - pred({alm['predespacho']}) = {esperado}"
                )


class TestSinArchivo:
    def test_health_sin_datos(self):
        servicio_stock._datos_general = {}
        servicio_stock._items_general = []
        respuesta = client.get("/api/v1/health")
        assert respuesta.status_code == 200
        assert respuesta.json()["cache_skus"] == 0
