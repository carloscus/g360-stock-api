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


class TestCatalogList:
    def test_listar_sin_catalogo(self):
        catalog_service._catalog = {}
        catalog_service._fecha_carga = None

        respuesta = client.get("/api/v1/catalog")
        assert respuesta.status_code == 200
        datos = respuesta.json()
        assert datos["metadata"]["cargado"] is False
        assert datos["metadata"]["total_skus"] == 0
        assert datos["items"] == []

    @pytest.mark.skipif(not RUTA_CATALOGO.exists(), reason="No hay archivo de catalogo")
    def test_listar_catalogo(self):
        with open(RUTA_CATALOGO, encoding="utf-8") as f:
            data = json.load(f)
        catalog_service.cargar_desde_json(data)

        respuesta = client.get("/api/v1/catalog")
        assert respuesta.status_code == 200
        datos = respuesta.json()
        total = datos["metadata"]["total_skus"]
        assert total == catalog_service.total_skus > 0
        items = datos["items"]
        assert len(items) == total

        required = {"sku", "nombre", "linea", "grupo", "tipo", "familia", "categoria",
                    "estado_linea", "un_bx", "peso_kg", "precio", "ean13", "ean14",
                    "keywords", "orden", "descontinuado"}
        assert required.issubset(set(items[0].keys()))
        assert all("almacenes" not in it for it in items)

        # Ordenado por orden del maestro (ignorando los sin orden)
        ordens = [it["orden"] for it in items if it["orden"] != 0]
        assert ordens == sorted(ordens)

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
        """Verificar que /stock retorna campos del catalogo cuando esta cargado."""
        # Cargar catalogo
        with open(RUTA_CATALOGO, encoding="utf-8") as f:
            data = json.load(f)
        catalog_service.cargar_desde_json(data)

        # Usar datos en cache (general o sucursales)
        from app.services.s1_service import servicio_stock
        if not servicio_stock._items_general:
            servicio_stock._actualizar_desde_origen("general")

        if not servicio_stock._items_general:
            pytest.skip("No hay datos en cache para probar")

        respuesta = client.get("/api/v1/stock?limit=1")
        assert respuesta.status_code == 200
        datos = respuesta.json()
        assert datos["metadata"]["enriquecido"] is True
        assert len(datos["items"]) >= 1

        # Verificar que los items tienen campos enrich
        item = datos["items"][0]
        assert "un_bx" in item
        assert "precio" in item
        assert "ean13" in item
        assert "keywords" in item

        # Limpiar
        catalog_service._catalog = {}
        catalog_service._fecha_carga = None

    @pytest.mark.skipif(not RUTA_CATALOGO.exists(), reason="No hay archivo de catalogo")
    def test_sku_con_enrich(self):
        """Verificar que /stock/{sku} retorna campos del catalogo cuando esta cargado."""
        import json as _json
        with open(RUTA_CATALOGO, encoding="utf-8") as f:
            data = _json.load(f)
        catalog_service.cargar_desde_json(data)

        # Cargar stock de prueba
        from app.services.s1_service import servicio_stock
        sample = Path(__file__).parent / "samples" / "REPT_STOCK_SAMPLE.xls"
        if sample.exists():
            servicio_stock.procesar_archivo_local(str(sample))
        if not servicio_stock._items_general:
            pytest.skip("No hay datos de stock cargados")

        respuesta = client.get("/api/v1/stock?limit=1")
        assert respuesta.status_code == 200
        datos = respuesta.json()
        assert len(datos["items"]) >= 1
        item = datos["items"][0]
        assert "un_bx" in item
        assert "keywords" in item

        # Limpiar
        catalog_service._catalog = {}
        catalog_service._fecha_carga = None


class TestCargarDesdeUrl:
    def test_cargar_desde_url_exitoso(self, monkeypatch):
        """Cargar_desde_url debe descargar y cargar un catalogo valido."""
        import httpx

        payload = {
            "productos": [
                {"sku": "011019", "un_bx": 60, "peso_kg": 0.2, "precio": 9.16, "estado_linea": "NACIONAL"},
                {"sku": "011028", "un_bx": 12, "peso_kg": 0.3, "precio": 11.5, "estado_linea": "NACIONAL"},
            ]
        }

        class FakeResponse:
            def raise_for_status(self):
                pass

            def json(self):
                return payload

        def fake_get(url, timeout=30):
            assert "catalogo_productos.json" in url
            return FakeResponse()

        monkeypatch.setattr(httpx, "get", fake_get)

        catalog_service._catalog = {}
        catalog_service._fecha_carga = None

        resultado = catalog_service.cargar_desde_url("https://example.com/catalogo_productos.json")
        assert resultado["ok"] is True
        assert resultado["total_skus"] == 2
        assert catalog_service.cargado
        assert catalog_service.buscar("011019")["un_bx"] == 60

        # Limpiar
        catalog_service._catalog = {}
        catalog_service._fecha_carga = None

    def test_cargar_desde_url_falla(self, monkeypatch):
        """Si la descarga falla, no debe romper y reporta error."""
        import httpx

        class FakeError(Exception):
            pass

        def fake_get(url, timeout=30):
            raise httpx.NetworkError("sin red", request=None)

        monkeypatch.setattr(httpx, "get", fake_get)

        catalog_service._catalog = {}
        catalog_service._fecha_carga = None

        resultado = catalog_service.cargar_desde_url("https://example.com/catalogo_productos.json")
        assert resultado["ok"] is False
        assert "error" in resultado
        assert not catalog_service.cargado


class TestSkuSinStock:
    """SKU en catalogo pero ausente del reporte de stock -> ficha con sin_stock."""

    def test_sku_en_catalogo_sin_stock_retorna_ficha(self, monkeypatch):
        from app.services.catalog_service import catalog_service as cat
        from app.services.s1_service import servicio_stock

        cat._catalog = {"76250": {
            "sku": "76250", "nombre": "BOLIGRAFO VINIFAN TRIFAN 32 M NEGRO DISPLAY X50",
            "un_bx": 28, "precio": 17.77, "linea": "ESCRITURA",
            "grupo": "BOLIGRAFO", "tipo": "DISPLAY", "familia": "TINTA SECA",
            "categoria": "VINIFAN", "ean13": "7754807762502", "ean14": "17754807762509",
            "keywords": [], "orden": 588, "estado_linea": "NUEVO", "peso_kg": 0.0,
            "nombre_corto": "Boligrafo Trifan 32 M Negro Display X50",
        }}
        cat._fecha_carga = None
        # Vaciar stock para que el fallback sea el unico camino
        servicio_stock._items_general = []
        servicio_stock._items_sucursales = []
        servicio_stock._enriched_general = []
        servicio_stock._enriched_sucursales = []
        servicio_stock._rebuild_todas()

        item = servicio_stock.obtener_sku_enriched("76250")
        assert item is not None
        assert item.sin_stock is True
        assert item.almacenes == []
        assert item.un_bx == 28
        assert item.precio == 17.77
        assert item.sku == "76250"

    def test_sku_inexistente_devuelve_none(self):
        from app.services.catalog_service import catalog_service as cat
        from app.services.s1_service import servicio_stock

        cat._catalog = {}
        servicio_stock._items_general = []
        servicio_stock._items_sucursales = []
        servicio_stock._enriched_general = []
        servicio_stock._enriched_sucursales = []
        servicio_stock._rebuild_todas()

        assert servicio_stock.obtener_sku_enriched("ZZZZZ99") is None

    def test_sku_en_stock_sin_cambiar_flags(self):
        """Un SKU presente en el reporte no debe marcar sin_stock."""
        from app.services.catalog_service import catalog_service as cat
        from app.services.s1_service import servicio_stock

        cat._catalog = {}
        item = servicio_stock.obtener_sku_enriched("0123ABC")
        if item is not None:
            assert item.sin_stock is False
            assert item.sin_catalogo is True


class TestDescontinuado:
    """El marcador descontinuado debe viajar catalogo -> enrich -> JSON."""

    @staticmethod
    def _cargar(catalogo):
        from datetime import datetime, timezone

        from app.services.catalog_service import catalog_service as cat
        cat._catalog = catalogo
        # Fecha fresca: evita el refresh remoto (sin red en tests)
        cat._fecha_carga = datetime.now(timezone.utc)

    @staticmethod
    def _limpiar():
        from app.services.catalog_service import catalog_service as cat
        cat._catalog = {}
        cat._fecha_carga = None

    def test_enrich_propaga_marcador(self):
        from app.models.schemas import ItemStock
        from app.services.s1_service import servicio_stock
        try:
            self._cargar({
                "79050": {"sku": "79050", "nombre": "TIJERA", "descontinuado": True},
                "011019": {"sku": "011019", "nombre": "PELOTA", "descontinuado": False},
            })
            items = servicio_stock._enriquecer_items(
                [ItemStock(sku="79050"), ItemStock(sku="011019"), ItemStock(sku="NADIE")])
            por_sku = {i.sku: i for i in items}
            assert por_sku["79050"].descontinuado is True
            assert por_sku["011019"].descontinuado is False
            # Sin catalogo: default False
            assert por_sku["NADIE"].descontinuado is False
            assert por_sku["NADIE"].sin_catalogo is True
        finally:
            self._limpiar()

    def test_ficha_sin_stock_propaga_marcador(self):
        from app.services.s1_service import servicio_stock
        try:
            self._cargar({
                "79050": {"sku": "79050", "nombre": "TIJERA", "descontinuado": True},
            })
            item = servicio_stock._item_desde_catalogo("79050")
            assert item is not None
            assert item.sin_stock is True
            assert item.descontinuado is True
        finally:
            self._limpiar()

    def test_upload_cuenta_descontinuados(self):
        respuesta = client.post(
            "/api/v1/catalog/upload",
            files={"archivo": ("catalogo_productos.json",
                               ('{"productos": [{"sku": "A", "descontinuado": true},'
                                ' {"sku": "B"}]}'),
                               "application/json")}
        )
        assert respuesta.status_code == 200
        try:
            datos = respuesta.json()
            assert datos["total_skus"] == 2
            assert datos["descontinuados"] == 1
        finally:
            self._limpiar()


class TestLineaCodigo:
    """linea_codigo del catalogo manda sobre el heurístico sku[:2]."""

    @staticmethod
    def _cargar(catalogo):
        from datetime import datetime, timezone

        from app.services.catalog_service import catalog_service as cat
        cat._catalog = catalogo
        cat._fecha_carga = datetime.now(timezone.utc)

    @staticmethod
    def _limpiar():
        from app.services.catalog_service import catalog_service as cat
        cat._catalog = {}
        cat._fecha_carga = None

    def test_ficha_sin_stock_prefiere_linea_codigo(self):
        from app.services.s1_service import servicio_stock
        try:
            self._cargar({
                "05001": {"sku": "05001", "nombre": "ARCHIVO A4",
                          "linea": "ARCHIVO", "linea_codigo": "78"},
                "01234": {"sku": "01234", "nombre": "BOLI", "linea": "PELOTAS"},
            })
            archivo = servicio_stock._item_desde_catalogo("05001")
            pelota = servicio_stock._item_desde_catalogo("01234")
            assert archivo is not None and archivo.linea_id == "78"
            assert archivo.linea == "ARCHIVO"
            # Sin linea_codigo: heurístico sku[:2]
            assert pelota is not None and pelota.linea_id == "01"
        finally:
            self._limpiar()

    def test_enriquecer_prefiere_linea_codigo_sin_codigo_reporte(self):
        from app.models.schemas import ItemStock
        from app.services.s1_service import servicio_stock
        try:
            self._cargar({
                "05001": {"sku": "05001", "nombre": "ARCHIVO A4",
                          "linea": "ARCHIVO", "linea_codigo": "78"},
            })
            items = servicio_stock._enriquecer_items(
                [ItemStock(sku="05001", linea="")])
            assert items[0].linea_id == "78"
        finally:
            self._limpiar()
