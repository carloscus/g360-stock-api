"""Tests para el endpoint de catalogo (upload + health)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.catalog_service import catalog_service

client = TestClient(app)
RUTA_CATALOGO = (
    Path(__file__).parent.parent.parent
    / "g360-master-data"
    / "output"
    / "catalogo_productos.json"
)


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

        required = {
            "sku",
            "nombre",
            "linea",
            "grupo",
            "tipo",
            "familia",
            "categoria",
            "estado_linea",
            "un_bx",
            "peso_kg",
            "precio",
            "ean13",
            "ean14",
            "keywords",
            "orden",
            "descontinuado",
        }
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
            files={"archivo": ("test.txt", b"hello", "text/plain")},
        )
        assert respuesta.status_code == 400
        assert "Formato no soportado" in respuesta.json()["detail"]

    @pytest.mark.skipif(not RUTA_CATALOGO.exists(), reason="No hay archivo de catalogo")
    def test_upload_catalogo_valido(self):
        with open(RUTA_CATALOGO, encoding="utf-8") as f:
            contenido = f.read()

        respuesta = client.post(
            "/api/v1/catalog/upload",
            files={
                "archivo": ("catalogo_productos.json", contenido, "application/json")
            },
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
                {
                    "sku": "011019",
                    "un_bx": 60,
                    "peso_kg": 0.2,
                    "precio": 9.16,
                    "estado_linea": "NACIONAL",
                },
                {
                    "sku": "011028",
                    "un_bx": 12,
                    "peso_kg": 0.3,
                    "precio": 11.5,
                    "estado_linea": "NACIONAL",
                },
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

        resultado = catalog_service.cargar_desde_url(
            "https://example.com/catalogo_productos.json"
        )
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

        resultado = catalog_service.cargar_desde_url(
            "https://example.com/catalogo_productos.json"
        )
        assert resultado["ok"] is False
        assert "error" in resultado
        assert not catalog_service.cargado


class TestSkuSinStock:
    """SKU en catalogo pero ausente del reporte de stock -> ficha con sin_stock."""

    def test_sku_en_catalogo_sin_stock_retorna_ficha(self, monkeypatch):
        from app.services.catalog_service import catalog_service as cat
        from app.services.s1_service import servicio_stock

        cat._catalog = {
            "76250": {
                "sku": "76250",
                "nombre": "BOLIGRAFO VINIFAN TRIFAN 32 M NEGRO DISPLAY X50",
                "un_bx": 28,
                "precio": 17.77,
                "linea": "ESCRITURA",
                "grupo": "BOLIGRAFO",
                "tipo": "DISPLAY",
                "familia": "TINTA SECA",
                "categoria": "VINIFAN",
                "ean13": "7754807762502",
                "ean14": "17754807762509",
                "keywords": [],
                "orden": 588,
                "estado_linea": "NUEVO",
                "peso_kg": 0.0,
                "nombre_corto": "Boligrafo Trifan 32 M Negro Display X50",
            }
        }
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
            self._cargar(
                {
                    "79050": {
                        "sku": "79050",
                        "nombre": "TIJERA",
                        "descontinuado": True,
                    },
                    "011019": {
                        "sku": "011019",
                        "nombre": "PELOTA",
                        "descontinuado": False,
                    },
                }
            )
            items = servicio_stock._enriquecer_items(
                [
                    ItemStock(sku="79050"),
                    ItemStock(sku="011019"),
                    ItemStock(sku="NADIE"),
                ]
            )
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
            self._cargar(
                {
                    "79050": {
                        "sku": "79050",
                        "nombre": "TIJERA",
                        "descontinuado": True,
                    },
                }
            )
            item = servicio_stock._item_desde_catalogo("79050")
            assert item is not None
            assert item.sin_stock is True
            assert item.descontinuado is True
        finally:
            self._limpiar()

    def test_upload_cuenta_descontinuados(self):
        respuesta = client.post(
            "/api/v1/catalog/upload",
            files={
                "archivo": (
                    "catalogo_productos.json",
                    (
                        '{"productos": [{"sku": "A", "descontinuado": true},'
                        ' {"sku": "B"}]}'
                    ),
                    "application/json",
                )
            },
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
            self._cargar(
                {
                    "05001": {
                        "sku": "05001",
                        "nombre": "ARCHIVO A4",
                        "linea": "78",
                        "linea_nombre": "ARCHIVO",
                        "linea_codigo": "78",
                    },
                    "01234": {
                        "sku": "01234",
                        "nombre": "BOLI",
                        "linea": "01",
                        "linea_nombre": "PELOTAS",
                    },
                }
            )
            archivo = servicio_stock._item_desde_catalogo("05001")
            pelota = servicio_stock._item_desde_catalogo("01234")
            assert archivo is not None and archivo.linea_id == "78"
            # linea_display: codigo + nombre legible
            assert archivo.linea == "78 - ARCHIVO"
            # Sin linea_codigo: heurístico sku[:2]
            assert pelota is not None and pelota.linea_id == "01"
        finally:
            self._limpiar()

    def test_enriquecer_prefiere_linea_codigo_sin_codigo_reporte(self):
        from app.models.schemas import ItemStock
        from app.services.s1_service import servicio_stock

        try:
            self._cargar(
                {
                    "05001": {
                        "sku": "05001",
                        "nombre": "ARCHIVO A4",
                        "linea": "ARCHIVO",
                        "linea_codigo": "78",
                    },
                }
            )
            items = servicio_stock._enriquecer_items([ItemStock(sku="05001", linea="")])
            assert items[0].linea_id == "78"
        finally:
            self._limpiar()


class TestLineaNombre:
    """El catalogo publica `linea` como codigo y `linea_nombre` como nombre.

    Antes el catalogo publicaba `linea` = NOMBRE y `linea_codigo` = CODIGO:
    cada consumidor lo interpretaba distinto y la misma linea aparecia
    como nombre o como codigo.
    """

    @staticmethod
    def _cargar(catalogo, meta=None):
        from datetime import datetime, timezone

        from app.services.catalog_service import catalog_service as cat

        cat._catalog = catalogo
        cat._meta = meta or {}
        cat._fecha_carga = datetime.now(timezone.utc)

    @staticmethod
    def _limpiar():
        from app.services.catalog_service import catalog_service as cat

        cat._catalog = {}
        cat._meta = {}
        cat._fecha_carga = None

    def test_no_duplica_el_nombre_de_linea(self):
        """Si el XLS ya trae el nombre, no se repite 'ARCHIVO - ARCHIVO'."""
        from app.models.schemas import ItemStock
        from app.services.s1_service import servicio_stock

        try:
            self._cargar(
                {
                    "05001": {
                        "sku": "05001",
                        "nombre": "ARCHIVO A4",
                        "linea": "78",
                        "linea_nombre": "ARCHIVO",
                        "linea_codigo": "78",
                    },
                }
            )
            items = servicio_stock._enriquecer_items(
                [ItemStock(sku="05001", linea="ARCHIVO")]
            )
            assert items[0].linea == "ARCHIVO"
        finally:
            self._limpiar()

    def test_completa_codigo_con_nombre_del_catalogo(self):
        """Si el XLS trae solo el codigo, se agrega el nombre del catalogo."""
        from app.models.schemas import ItemStock
        from app.services.s1_service import servicio_stock

        try:
            self._cargar(
                {
                    "05001": {
                        "sku": "05001",
                        "nombre": "ARCHIVO A4",
                        "linea": "78",
                        "linea_nombre": "ARCHIVO",
                        "linea_codigo": "78",
                    },
                }
            )
            items = servicio_stock._enriquecer_items(
                [ItemStock(sku="05001", linea="78")]
            )
            assert items[0].linea == "78 - ARCHIVO"
            assert items[0].linea_id == "78"
        finally:
            self._limpiar()

    def test_linea_id_usa_la_linea_canonica_del_catalogo(self):
        """Sin linea_codigo, se usa `linea` (ya es codigo) antes que sku[:2]."""
        from app.models.schemas import ItemStock
        from app.services.s1_service import servicio_stock

        try:
            self._cargar(
                {
                    "CA008": {
                        "sku": "CA008",
                        "nombre": "COLORES",
                        "linea": "77",
                        "linea_nombre": "PINTURA",
                    },
                }
            )
            items = servicio_stock._enriquecer_items([ItemStock(sku="CA008", linea="")])
            # sku[:2] seria "CA" (no es una linea): debe ganar el catalogo
            assert items[0].linea_id == "77"
        finally:
            self._limpiar()

    def test_nombre_de_linea_expuesto(self):
        """El item del catalogo trae el nombre legible de la linea."""
        from fastapi.testclient import TestClient

        from app.main import app

        try:
            self._cargar(
                {
                    "05001": {
                        "sku": "05001",
                        "nombre": "X",
                        "linea": "78",
                        "linea_nombre": "ARCHIVO",
                    }
                },
                meta={"lineas_nombre_a_codigo": {"ARCHIVO": "78"}},
            )
            cliente = TestClient(app)
            r = cliente.get("/api/v1/catalog")
            assert r.status_code == 200
            datos = r.json()
            assert datos["items"][0]["linea"] == "78"
            assert datos["items"][0]["linea_nombre"] == "ARCHIVO"
            assert datos["metadata"]["lineas_nombre_a_codigo"] == {"ARCHIVO": "78"}
        finally:
            self._limpiar()

    def test_estado_linea_no_cae_al_grupo(self):
        """El GRUPO del producto no es un estado de linea.

        La guia ERP (SKU_BX) define 4 estados: NUEVO, IMPORTADO,
        TRADICIONAL y NACIONAL. Antes, cuando el catalogo no traia estado,
        se rellenaba con el grupo y "TAJADORES" / "RESALTADORES" terminaban
        como estados, ensuciando la segmentacion.
        """
        from app.models.schemas import ItemStock
        from app.services.s1_service import servicio_stock

        try:
            self._cargar(
                {
                    "79026": {
                        "sku": "79026",
                        "nombre": "TIJERA VINIFAN PANDA",
                        "linea": "79",
                        "linea_nombre": "ACCESORIOS",
                        "grupo": "TIJERAS",
                        "categoria": "VINIFAN",
                    },
                }
            )
            items = servicio_stock._enriquecer_items(
                [ItemStock(sku="79026", linea="79 - ACCESORIOS", grupo="02 - TIJERAS")]
            )
            assert items[0].estado_linea == ""
            # el grupo sigue disponible en su propia columna
            assert items[0].grupo == "02 - TIJERAS"
        finally:
            self._limpiar()

    def test_estado_linea_del_catalogo_se_respeta(self):
        """Si el catalogo trae estado_linea, ese manda."""
        from app.models.schemas import ItemStock
        from app.services.s1_service import servicio_stock

        try:
            self._cargar(
                {
                    "79026": {
                        "sku": "79026",
                        "nombre": "TIJERA",
                        "linea": "79",
                        "estado_linea": "NUEVO",
                        "grupo": "TIJERAS",
                    },
                }
            )
            items = servicio_stock._enriquecer_items(
                [ItemStock(sku="79026", linea="79 - ACCESORIOS")]
            )
            assert items[0].estado_linea == "NUEVO"
        finally:
            self._limpiar()

    def test_taxonomia_publicada_en_el_catalogo(self):
        """La taxonomia viaja en el metadata: no hay que duplicarla."""
        from fastapi.testclient import TestClient

        from app.main import app

        try:
            self._cargar(
                {"05001": {"sku": "05001", "nombre": "X", "linea": "78"}},
                meta={"categorias_por_linea": {"78": "VINIFAN"}},
            )
            cliente = TestClient(app)
            r = cliente.get("/api/v1/catalog")
            assert r.status_code == 200
            meta = r.json()["metadata"]
            assert meta["categorias_por_linea"] == {"78": "VINIFAN"}
        finally:
            self._limpiar()


class TestLineaAmbiguaMandaCatalogo:
    """Un NOMBRE de linea ambiguo ('ACCESORIOS' = 79 y CD) no resuelve solo.

    El S1 trae '79 - ACCESORIOS' tanto para las tijeras (linea 79) como para
    los pinceles Crayola (linea CD). El catalogo ya desambigua por grupo y
    publica el `linea_codigo` correcto: ese debe mandar.
    """

    @staticmethod
    def _cargar(catalogo, meta=None):
        from datetime import datetime, timezone

        from app.services.catalog_service import catalog_service as cat

        cat._catalog = catalogo
        cat._meta = meta or {}
        cat._fecha_carga = datetime.now(timezone.utc)

    @staticmethod
    def _limpiar():
        from app.services.catalog_service import catalog_service as cat

        cat._catalog = {}
        cat._meta = {}
        cat._fecha_carga = None

    def test_pincel_crayola_toma_la_linea_cd_del_catalogo(self):
        """El S1 dice '79 - ACCESORIOS' pero el catalogo dice CD: gana CD."""
        from app.models.schemas import ItemStock
        from app.services.s1_service import servicio_stock

        try:
            self._cargar(
                {
                    "CD001": {
                        "sku": "CD001",
                        "nombre": "CRAYOLA PINCELES",
                        "linea": "CD",
                        "linea_codigo": "CD",
                        "linea_nombre": "ACCESORIOS",
                        "grupo": "PINCELES",
                    },
                }
            )
            items = servicio_stock._enriquecer_items(
                [ItemStock(sku="CD001", linea="79 - ACCESORIOS")]
            )
            assert items[0].linea_id == "CD"
            assert items[0].linea == "CD - ACCESORIOS"
        finally:
            self._limpiar()

    def test_tijera_sigue_en_79_por_el_catalogo(self):
        """El S1 dice '79 - ACCESORIOS' y el catalogo tambien: sigue 79."""
        from app.models.schemas import ItemStock
        from app.services.s1_service import servicio_stock

        try:
            self._cargar(
                {
                    "79026": {
                        "sku": "79026",
                        "nombre": "TIJERA VINIFAN PANDA",
                        "linea": "79",
                        "linea_codigo": "79",
                        "linea_nombre": "ACCESORIOS",
                        "grupo": "TIJERAS",
                    },
                }
            )
            items = servicio_stock._enriquecer_items(
                [ItemStock(sku="79026", linea="79 - ACCESORIOS")]
            )
            assert items[0].linea_id == "79"
            assert items[0].linea == "79 - ACCESORIOS"
        finally:
            self._limpiar()

    def test_nombre_no_ambiguo_respeta_la_linea_del_s1(self):
        """Un nombre NO ambiguo no se toca: el S1 manda."""
        from app.models.schemas import ItemStock
        from app.services.s1_service import servicio_stock

        try:
            self._cargar(
                {
                    "05001": {
                        "sku": "05001",
                        "nombre": "ARCHIVO A4",
                        "linea": "78",
                        "linea_codigo": "78",
                        "linea_nombre": "ARCHIVO",
                    },
                }
            )
            items = servicio_stock._enriquecer_items(
                [ItemStock(sku="05001", linea="78 - ARCHIVO")]
            )
            assert items[0].linea_id == "78"
        finally:
            self._limpiar()

    def test_sin_catalogo_conserva_la_linea_del_s1(self):
        """Sin catalogo no hay desambiguacion posible: se conserva el S1."""
        from app.models.schemas import ItemStock
        from app.services.s1_service import servicio_stock

        try:
            self._cargar({})
            items = servicio_stock._enriquecer_items(
                [ItemStock(sku="CD001", linea="79 - ACCESORIOS")]
            )
            # Sin catalogo: el nombre ambiguo no puede resolverse,
            # se conserva el sufijo del SKU ("CD") como fallback
            assert items[0].linea_id == "CD"
        finally:
            self._limpiar()


class TestLineaAmbiguaRobustez:
    """Un NOMBRE ambiguo NUEVO no debe romper ni mal-asignar la linea.

    La lista de nombres ambiguos es extensible: si manana aparece otro nombre
    que designa a mas de una linea, el mecanismo (catalogo manda) debe seguir
    funcionando sin tocar la logica de merge.
    """

    @staticmethod
    def _cargar(catalogo, meta=None):
        from datetime import datetime, timezone

        from app.services.catalog_service import catalog_service as cat

        cat._catalog = catalogo
        cat._meta = meta or {}
        cat._fecha_carga = datetime.now(timezone.utc)

    @staticmethod
    def _limpiar():
        from app.services.catalog_service import catalog_service as cat

        cat._catalog = {}
        cat._meta = {}
        cat._fecha_carga = None

    def test_nombre_ambiguo_sin_catalogo_no_rompe(self):
        """El S1 trae un nombre ambiguo y no hay catalogo: no debe reventar."""
        from app.models.schemas import ItemStock
        from app.services.s1_service import servicio_stock

        try:
            self._cargar({})
            items = servicio_stock._enriquecer_items(
                [ItemStock(sku="XX001", linea="00 - ACCESORIOS")]
            )
            # No hay catalogo: se conserva lo mejor posible, sin excepcion.
            assert items[0].linea_id is not None
        finally:
            self._limpiar()

    def test_catalogo_sin_linea_codigo_cae_a_linea(self):
        """Si el catalogo no trae linea_codigo, usa su `linea` canonica."""
        from app.models.schemas import ItemStock
        from app.services.s1_service import servicio_stock

        try:
            self._cargar(
                {
                    "CD001": {
                        "sku": "CD001",
                        "nombre": "CRAYOLA",
                        "linea": "CD",
                        "linea_nombre": "ACCESORIOS",
                    },
                }
            )
            items = servicio_stock._enriquecer_items(
                [ItemStock(sku="CD001", linea="79 - ACCESORIOS")]
            )
            assert items[0].linea_id == "CD"
        finally:
            self._limpiar()

    def test_sku_nuevo_sin_catalogo_usa_prefijo(self):
        """Un SKU nuevo (fuera del catalogo) cae al prefijo del SKU, sin error."""
        from app.models.schemas import ItemStock
        from app.services.s1_service import servicio_stock

        try:
            self._cargar({})
            items = servicio_stock._enriquecer_items([ItemStock(sku="ZZ123", linea="")])
            assert items[0].linea_id in ("ZZ", None) or items[0].linea_id == "ZZ"
        finally:
            self._limpiar()

    def test_crayola_CA_toma_linea_del_catalogo(self):
        """CA001 viene de S1 como '77 - PINTURA' pero el catalogo dice CA."""
        from app.models.schemas import ItemStock
        from app.services.s1_service import servicio_stock

        try:
            self._cargar(
                {
                    "CA001": {
                        "sku": "CA001",
                        "nombre": "CRAYOLA CRAYONES DELGADOS",
                        "linea": "CA",
                        "linea_codigo": "CA",
                        "linea_nombre": "PINTURA",
                        "grupo": "CRAYONES",
                        "categoria": "REPRESENTADAS",
                    },
                }
            )
            items = servicio_stock._enriquecer_items(
                [ItemStock(sku="CA001", linea="77 - PINTURA", grupo="CRAYONES")]
            )
            assert items[0].linea_id == "CA"
            assert items[0].categoria == "REPRESENTADAS"
        finally:
            self._limpiar()

    def test_crayola_CB_toma_linea_del_catalogo(self):
        """CB007 viene de S1 como '76 - ESCRITURA' pero el catalogo dice CB."""
        from app.models.schemas import ItemStock
        from app.services.s1_service import servicio_stock

        try:
            self._cargar(
                {
                    "CB007": {
                        "sku": "CB007",
                        "nombre": "CRAYOLA BOLIGRAFOS",
                        "linea": "CB",
                        "linea_codigo": "CB",
                        "linea_nombre": "ESCRITURA",
                        "grupo": "BOLIGRAFOS",
                        "categoria": "REPRESENTADAS",
                    },
                }
            )
            items = servicio_stock._enriquecer_items(
                [ItemStock(sku="CB007", linea="76 - ESCRITURA", grupo="BOLIGRAFOS")]
            )
            assert items[0].linea_id == "CB"
            assert items[0].categoria == "REPRESENTADAS"
        finally:
            self._limpiar()

    def test_crayola_CC_toma_linea_del_catalogo(self):
        """CC001 viene de S1 como 'PEGAMENTOS' pero el catalogo dice CC."""
        from app.models.schemas import ItemStock
        from app.services.s1_service import servicio_stock

        try:
            self._cargar(
                {
                    "CC001": {
                        "sku": "CC001",
                        "nombre": "CRAYOLA GOMA ESCARCHADA",
                        "linea": "CC",
                        "linea_codigo": "CC",
                        "linea_nombre": "PEGAMENTOS",
                        "grupo": "GOMA ESCARCHADA",
                        "categoria": "REPRESENTADAS",
                    },
                }
            )
            items = servicio_stock._enriquecer_items(
                [ItemStock(sku="CC001", linea="PEGAMENTOS", grupo="GOMA ESCARCHADA")]
            )
            assert items[0].linea_id == "CC"
            assert items[0].categoria == "REPRESENTADAS"
        finally:
            self._limpiar()

    def test_crayola_CE_toma_linea_del_catalogo(self):
        """CE001 viene de S1 como 'MANUALIDADES' pero el catalogo dice CE."""
        from app.models.schemas import ItemStock
        from app.services.s1_service import servicio_stock

        try:
            self._cargar(
                {
                    "CE001": {
                        "sku": "CE001",
                        "nombre": "CRAYOLA TIZAS JUMBO",
                        "linea": "CE",
                        "linea_codigo": "CE",
                        "linea_nombre": "MANUALIDADES",
                        "grupo": "TIZAS",
                        "categoria": "REPRESENTADAS",
                    },
                }
            )
            items = servicio_stock._enriquecer_items(
                [ItemStock(sku="CE001", linea="MANUALIDADES", grupo="TIZAS")]
            )
            assert items[0].linea_id == "CE"
            assert items[0].categoria == "REPRESENTADAS"
        finally:
            self._limpiar()

    def test_crayola_CF_toma_linea_del_catalogo(self):
        """CF005 viene de S1 como 'SET' pero el catalogo dice CF."""
        from app.models.schemas import ItemStock
        from app.services.s1_service import servicio_stock

        try:
            self._cargar(
                {
                    "CF005": {
                        "sku": "CF005",
                        "nombre": "CRAYOLA SET DE PINTURA",
                        "linea": "CF",
                        "linea_codigo": "CF",
                        "linea_nombre": "SET",
                        "grupo": "SET",
                        "categoria": "REPRESENTADAS",
                    },
                }
            )
            items = servicio_stock._enriquecer_items(
                [ItemStock(sku="CF005", linea="SET", grupo="SET")]
            )
            assert items[0].linea_id == "CF"
            assert items[0].categoria == "REPRESENTADAS"
        finally:
            self._limpiar()

    def test_vinifan_no_se_ve_afectado_por_fix_crayola(self):
        """79102 es VINIFAN y no debe cambiar aRepresentadas."""
        from app.models.schemas import ItemStock
        from app.services.s1_service import servicio_stock

        try:
            self._cargar(
                {
                    "79102": {
                        "sku": "79102",
                        "nombre": "BORRADOR BLANCO CHICO VINIFAN",
                        "linea": "79",
                        "linea_codigo": "79",
                        "linea_nombre": "ACCESORIOS",
                        "grupo": "BORRADOR",
                        "categoria": "VINIFAN",
                    },
                }
            )
            items = servicio_stock._enriquecer_items(
                [ItemStock(sku="79102", linea="79 - ACCESORIOS", grupo="BORRADOR")]
            )
            assert items[0].linea_id == "79"
            assert items[0].categoria == "VINIFAN"
        finally:
            self._limpiar()

    def test_viniball_no_se_ve_afectado_por_fix_crayola(self):
        """011019 es VINIBALL y no debe cambiar."""
        from app.models.schemas import ItemStock
        from app.services.s1_service import servicio_stock

        try:
            self._cargar(
                {
                    "011019": {
                        "sku": "011019",
                        "nombre": "SEMIDEPORTIVA FUTBOL CRACKCITO",
                        "linea": "01",
                        "linea_codigo": "01",
                        "linea_nombre": "PELOTAS",
                        "grupo": "NACIONAL",
                        "categoria": "VINIBALL",
                    },
                }
            )
            items = servicio_stock._enriquecer_items(
                [ItemStock(sku="011019", linea="01 - PELOTAS", grupo="NACIONAL")]
            )
            assert items[0].linea_id == "01"
            assert items[0].categoria == "VINIBALL"
        finally:
            self._limpiar()

    def test_linea_85_no_se_ve_afectada_por_fix_crayola(self):
        """85007 es REPRESENTADAS de linea 85 y no debe cambiar."""
        from app.models.schemas import ItemStock
        from app.services.s1_service import servicio_stock

        try:
            self._cargar(
                {
                    "85007": {
                        "sku": "85007",
                        "nombre": "LIGAS #18 X 1/4LBS-NT-ALLEANZA",
                        "linea": "85",
                        "linea_codigo": "85",
                        "linea_nombre": "REPRESENTADAS",
                        "grupo": "OLFA",
                        "categoria": "REPRESENTADAS",
                    },
                }
            )
            items = servicio_stock._enriquecer_items(
                [ItemStock(sku="85007", linea="85 - REPRESENTADAS", grupo="OLFA")]
            )
            assert items[0].linea_id == "85"
            assert items[0].categoria == "REPRESENTADAS"
        finally:
            self._limpiar()

    def test_sku_nuevo_C_sin_catalogo_usa_prefijo(self):
        """SKU nuevo que empieza con C y no esta en catalogo usa prefijo."""
        from app.models.schemas import ItemStock
        from app.services.s1_service import servicio_stock

        try:
            self._cargar({})  # Catálogo vacío
            items = servicio_stock._enriquecer_items(
                [ItemStock(sku="CA087", linea="77 - PINTURA", grupo="CRAYONES")]
            )
            # Con el fallback C*, debe usar CA
            assert items[0].linea_id == "CA"
        finally:
            self._limpiar()

    def test_sku_falso_positivo_C_no_es_Crayola(self):
        """SKU CIPSA interno que empieza con C pero no es Crayola."""
        from app.models.schemas import ItemStock
        from app.services.s1_service import servicio_stock

        try:
            # Simular que CC09150 NO está en catálogo
            self._cargar({})
            items = servicio_stock._enriquecer_items(
                [ItemStock(sku="CC09150", linea="72 - PEGAMENTOS", grupo="ETIQUETAS")]
            )
            # No tiene catálogo, no es Crayola reconocido (no tiene patrón),
            # debe caer al fallback: prefijo CC
            assert items[0].linea_id == "CC"
        finally:
            self._limpiar()

    def test_linea_ambigua_con_grupo_distinto_sigue_la_regla(self):
        """El desambiguado no depende del grupo en stock-api: confia en catalogo."""
        from app.models.schemas import ItemStock
        from app.services.s1_service import servicio_stock

        try:
            self._cargar(
                {
                    "79102": {
                        "sku": "79102",
                        "nombre": "BORRADOR",
                        "linea": "79",
                        "linea_codigo": "79",
                        "linea_nombre": "ACCESORIOS",
                        "grupo": "BORRADOR",
                    },
                }
            )
            items = servicio_stock._enriquecer_items(
                [ItemStock(sku="79102", linea="79 - ACCESORIOS")]
            )
            assert items[0].linea_id == "79"
        finally:
            self._limpiar()


class TestStockYCatalogoNoSeContradicen:
    """El flujo REAL del reporte: transform -> enriquecer.

    Los tests anteriores armaban el ItemStock a mano (sin categoria), asi que
    no cubrian el caso real: el reporte de S1 calcula la categoria con
    constants.py y esa categoria ganaba sobre la del catalogo. Con eso
    /stock decia VINIFAN para un Crayola de linea 76 mientras /catalog decia
    REPRESENTADAS. Estos tests pasan por _transformar_items, que es el camino
    que recorre el stock de verdad.
    """

    @staticmethod
    def _cargar(catalogo, meta=None):
        from datetime import datetime, timezone

        from app.services.catalog_service import catalog_service as cat

        cat._catalog = catalogo
        cat._meta = meta or {}
        cat._fecha_carga = datetime.now(timezone.utc)

    @staticmethod
    def _limpiar():
        from app.services.catalog_service import catalog_service as cat

        cat._catalog = {}
        cat._meta = {}
        cat._fecha_carga = None

    @staticmethod
    def _flujo_completo(sku, linea_s1, catalogo):
        """Reproduce: datos del reporte -> _transformar_items -> enriquecer."""
        from app.services.s1_service import servicio_stock

        datos = {
            "VES": {
                sku: {
                    "descripcion": f"PRODUCTO {sku}",
                    "um": "UND",
                    "linea": linea_s1,
                    "grupo": "GRUPO",
                    "tipo": "TIPO",
                    "familia": "FAMILIA",
                    "stock": 5,
                    "predespacho": 0,
                }
            }
        }
        items = servicio_stock._transformar_items(datos)
        return servicio_stock._enriquecer_items(items)

    def test_crayola_en_linea_72_queda_representadas(self):
        """CC001 viene de S1 como '72 - PEGAMENTOS' (categoria VINIFAN local)."""
        try:
            self._cargar(
                {
                    "CC001": {
                        "sku": "CC001",
                        "nombre": "CRAYOLA GOMA ESCARCHADA",
                        "linea": "CC",
                        "linea_codigo": "CC",
                        "linea_nombre": "PEGAMENTOS",
                        "grupo": "GOMA ESCARCHADA",
                        "categoria": "REPRESENTADAS",
                    },
                }
            )
            items = self._flujo_completo("CC001", "72 - PEGAMENTOS", None)
            assert items[0].categoria == "REPRESENTADAS"
            assert items[0].linea_id == "CC"
            assert items[0].linea.startswith("CC")
        finally:
            self._limpiar()

    def test_crayola_en_linea_76_queda_representadas(self):
        """CB001 viene de S1 como '76 - ESCRITURA'."""
        try:
            self._cargar(
                {
                    "CB001": {
                        "sku": "CB001",
                        "nombre": "CRAYOLA RESALTADOR",
                        "linea": "CB",
                        "linea_codigo": "CB",
                        "linea_nombre": "ESCRITURA",
                        "grupo": "RESALTADOR",
                        "categoria": "REPRESENTADAS",
                    },
                }
            )
            items = self._flujo_completo("CB001", "76 - ESCRITURA", None)
            assert items[0].categoria == "REPRESENTADAS"
            assert items[0].linea_id == "CB"
        finally:
            self._limpiar()

    def test_linea_ce_ya_no_es_vinifan(self):
        """CE (MANUALIDADES) es 100% Crayola: la taxonomia local lo refleja."""
        from app.core.constants import asignar_categoria

        assert asignar_categoria("CE") == "REPRESENTADAS"
        assert asignar_categoria("CF") == "REPRESENTADAS"
        assert asignar_categoria("CA") == "REPRESENTADAS"

    def test_categoria_del_catalogo_manda_sobre_la_local(self):
        """Si el catalogo dice otra cosa, manda el catalogo."""
        try:
            self._cargar(
                {
                    "X001": {
                        "sku": "X001",
                        "nombre": "PRODUCTO",
                        "linea": "78",
                        "linea_codigo": "78",
                        "linea_nombre": "ARCHIVO",
                        "grupo": "G",
                        "categoria": "REPRESENTADAS",
                    },
                }
            )
            items = self._flujo_completo("X001", "78 - ARCHIVO", None)
            # El catalogo (REPRESENTADAS) gana al calculo local (VINIFAN).
            assert items[0].categoria == "REPRESENTADAS"
        finally:
            self._limpiar()

    def test_sku_sin_catalogo_conserva_la_categoria_local(self):
        """Sin catalogo, el API sigue clasificando con su propia taxonomia."""
        try:
            self._cargar({})
            items = self._flujo_completo("X002", "78 - ARCHIVO", None)
            assert items[0].categoria == "VINIFAN"
            assert items[0].sin_catalogo is True
        finally:
            self._limpiar()

    def test_crayola_sin_catalogo_no_sale_vinifan(self):
        """Un C* que aun no esta en el catalogo sigue siendo REPRESENTADAS.

        Es la ventana dangerous: el Crayola entra al ERP, el catalogo aun no
        se regenero y el reporte lo trae en una linea generica (76). Si la
        marca no mandara, /stock lo reportaria como VINIFAN, que es
        exactamente el ruido que la regla busca evitar.
        """
        try:
            self._cargar({})
            items = self._flujo_completo("CB999", "76 - ESCRITURA", None)
            assert items[0].categoria == "REPRESENTADAS"
            assert items[0].linea_id == "CB"
        finally:
            self._limpiar()

    def test_sub_marca_crayola_nueva_sin_catalogo(self):
        """Una sub-marca Crayola nueva (CG) tampoco cae en OTROS."""
        try:
            self._cargar({})
            items = self._flujo_completo("CG500", "77 - PINTURA", None)
            assert items[0].categoria == "REPRESENTADAS"
            assert items[0].linea_id == "CG"
        finally:
            self._limpiar()


class TestFlagsDeNegocio:
    """Flags que publica g360-master-data (v3.6.0) y que /stock debe propagar.

    El catalogo es el allowlist real del API: un SKU con stock puede estar
    publicado sin precio (`por_activar`) o en la cuarta categoria
    (`revision_venta`). Si el API no propaga el flag, el frontend no tiene
    como saber por que un SKU aparece con precio 0.
    """

    @staticmethod
    def _cargar(catalogo, meta=None):
        from datetime import datetime, timezone

        from app.services.catalog_service import catalog_service as cat

        cat._catalog = catalogo
        cat._meta = meta or {}
        cat._fecha_carga = datetime.now(timezone.utc)

    @staticmethod
    def _limpiar():
        from app.services.catalog_service import catalog_service as cat

        cat._catalog = {}
        cat._meta = {}
        cat._fecha_carga = None

    @staticmethod
    def _producto(sku, **extra):
        base = {
            "sku": sku,
            "nombre": f"PRODUCTO {sku}",
            "linea": "78",
            "linea_codigo": "78",
            "linea_nombre": "ARCHIVO",
            "grupo": "FOLDER",
            "tipo": "FANTASIA",
            "familia": "OFICIO",
            "categoria": "VINIFAN",
            "categoria_venta": "VINIFAN",
            "precio": 4.5,
            "un_bx": 12,
            "keywords": [],
            "orden": 10,
            "en_guia": True,
            "compromiso": False,
            "cotizable": True,
            "por_activar": False,
            "vigente": True,
            "origen": "erp",
            "derivado_de": "",
        }
        base.update(extra)
        return base

    @staticmethod
    def _flujo(sku, linea_s1="0178 - ARCHIVO", stock=5, predespacho=0):
        from app.services.s1_service import servicio_stock

        datos = {
            "VES": {
                sku: {
                    "descripcion": f"PRODUCTO {sku}",
                    "um": "UND",
                    "linea": linea_s1,
                    "grupo": "03 - FOLDER",
                    "tipo": "01 - FANTASIA",
                    "familia": "02 - OFICIO",
                    "stock": stock,
                    "predespacho": predespacho,
                }
            }
        }
        return servicio_stock._enriquecer_items(
            servicio_stock._transformar_items(datos)
        )

    def test_flags_cotizable_se_propagan(self):
        try:
            self._cargar({"T001": self._producto("T001")})
            item = self._flujo("T001")[0]
            assert item.cotizable is True
            assert item.por_activar is False
            assert item.en_guia is True
            assert item.categoria_venta == "VINIFAN"
            assert item.origen == "erp"
            assert item.revision == ""
        finally:
            self._limpiar()

    def test_por_activar_cuando_no_hay_precio(self):
        try:
            self._cargar(
                {
                    "T002": self._producto(
                        "T002",
                        precio=0.0,
                        cotizable=False,
                        por_activar=True,
                        origen="s1",
                        en_guia=False,
                    )
                }
            )
            item = self._flujo("T002", linea_s1="0198 - PRODUCTOS SIN EMBALAJE")[0]
            assert item.precio == 0.0
            assert item.por_activar is True
            assert item.cotizable is False
            assert item.revision == "por_activar"
        finally:
            self._limpiar()

    def test_revision_venta_para_categoria_fuera_de_negocio(self):
        try:
            self._cargar(
                {
                    "T003": self._producto(
                        "T003",
                        categoria="MATERIALES",
                        categoria_venta="REVISION_VENTA",
                    )
                }
            )
            item = self._flujo("T003", linea_s1="0140 - MATERIALES")[0]
            assert item.categoria_venta == "REVISION_VENTA"
            assert item.revision == "revision_venta"
        finally:
            self._limpiar()

    def test_compromiso_se_propaga(self):
        try:
            self._cargar({"T004": self._producto("T004", compromiso=True)})
            item = self._flujo("T004", predespacho=3)[0]
            assert item.compromiso is True
            assert item.revision == "compromiso"
        finally:
            self._limpiar()

    def test_derivado_metodo_d_expone_la_base(self):
        try:
            self._cargar({"T005D": self._producto("T005D", derivado_de="T005")})
            item = self._flujo("T005D", linea_s1="0198 - PRODUCTOS SIN EMBALAJE")[0]
            assert item.derivado_de == "T005"
            assert item.cotizable is True
        finally:
            self._limpiar()

    def test_sin_catalogo_marca_revision(self):
        try:
            self._cargar({})
            item = self._flujo("T999", linea_s1="0178 - ARCHIVO")[0]
            assert item.sin_catalogo is True
            assert item.revision == "sin_catalogo"
            assert item.cotizable is False
        finally:
            self._limpiar()

    def test_normaliza_grupo_tipo_familia(self):
        """El S1 trae '03 - FOLDER'; /stock y /catalog deben mostrar 'FOLDER'."""
        try:
            self._cargar({})
            item = self._flujo("T998", linea_s1="0178 - ARCHIVO")[0]
            assert item.grupo == "FOLDER"
            assert item.tipo == "FANTASIA"
            assert item.familia == "OFICIO"
        finally:
            self._limpiar()


class TestStockCompacto:
    """Endpoint /api/v1/stock/skus: universo consolidado, sin almacenes."""

    def test_route_no_es_sombreado_por_stock_sku(self):
        """/api/v1/stock/skus debe responder el compacto, no 404 de /stock/{sku}."""
        from app.services.s1_service import servicio_stock
        from datetime import datetime, timezone

        original = servicio_stock._enriched_general
        original_refrescar = servicio_stock._refrescar_si_es_necesario
        original_fecha = servicio_stock._fecha_general
        try:
            servicio_stock._refrescar_si_es_necesario = lambda *a, **k: None
            servicio_stock._fecha_general = datetime.now(timezone.utc)
            servicio_stock._enriched_general = self._items()

            respuesta = client.get("/api/v1/stock/skus")
            assert respuesta.status_code == 200
            datos = respuesta.json()
            assert datos["metadata"]["total_skus"] == 2
            item = {i["sku"]: i for i in datos["items"]}["T100"]
            # Consolidado: el total no depende de cuantos almacenes tenga.
            assert item["stock"] == 12
            assert item["predespacho"] == 2
            assert item["disponible"] == 10
            assert item["linea_id"] == "78"
            assert item["categoria_venta"] == "VINIFAN"
            assert "almacenes" not in item
        finally:
            servicio_stock._enriched_general = original
            servicio_stock._refrescar_si_es_necesario = original_refrescar
            servicio_stock._fecha_general = original_fecha

    def test_solo_con_movimiento_omite_skus_sin_stock(self):
        from app.services.s1_service import servicio_stock
        from datetime import datetime, timezone

        original = servicio_stock._enriched_general
        original_refrescar = servicio_stock._refrescar_si_es_necesario
        original_fecha = servicio_stock._fecha_general
        try:
            servicio_stock._refrescar_si_es_necesario = lambda *a, **k: None
            servicio_stock._fecha_general = datetime.now(timezone.utc)
            servicio_stock._enriched_general = self._items(sin_stock=True)

            completo = servicio_stock.obtener_skus_compactos(solo_con_movimiento=False)
            movimientos = servicio_stock.obtener_skus_compactos(
                solo_con_movimiento=True
            )
            assert len(completo.items) == 3
            assert len(movimientos.items) == 2
            assert "T102" not in {i.sku for i in movimientos.items}
        finally:
            servicio_stock._enriched_general = original
            servicio_stock._refrescar_si_es_necesario = original_refrescar
            servicio_stock._fecha_general = original_fecha

    @staticmethod
    def _items(sin_stock=False):
        from app.models.schemas import AlmacenStock, ItemStockEnriched

        items = [
            ItemStockEnriched(
                sku="T100",
                descripcion="PRODUCTO T100",
                um="UND",
                linea="78 - ARCHIVO",
                linea_id="78",
                grupo="FOLDER",
                tipo="FANTASIA",
                familia="OFICIO",
                categoria="VINIFAN",
                categoria_venta="VINIFAN",
                almacenes=[
                    AlmacenStock(
                        almacen="VES",
                        stock=10,
                        predespacho=2,
                        disponible=8,
                    ),
                    AlmacenStock(
                        almacen="40",
                        stock=2,
                        predespacho=0,
                        disponible=2,
                    ),
                ],
            ),
            ItemStockEnriched(
                sku="T101",
                descripcion="PRODUCTO T101",
                um="CJA",
                linea="0198 - PRODUCTOS SIN EMBALAJE",
                linea_id="98",
                grupo="SIN EMBALAJE",
                tipo="",
                familia="",
                categoria="DESCARTE Y VARIOS",
                categoria_venta="REVISION_VENTA",
                sin_catalogo=True,
                almacenes=[
                    AlmacenStock(almacen="VES", stock=0, predespacho=4, disponible=0)
                ],
            ),
        ]
        if sin_stock:
            items.append(
                ItemStockEnriched(
                    sku="T102",
                    descripcion="PRODUCTO T102",
                    um="UND",
                    linea="78 - ARCHIVO",
                    linea_id="78",
                    almacenes=[
                        AlmacenStock(
                            almacen="VES", stock=0, predespacho=0, disponible=0
                        )
                    ],
                )
            )
        return items
