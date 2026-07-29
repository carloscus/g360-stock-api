from __future__ import annotations

from pathlib import Path

import pytest

from app.core.xls_fallback import leer_xls
from app.core.parsers import parsear_stock_desde_xls

RUTA_SAMPLE = Path(__file__).parent / "samples" / "REPT_STOCK_SAMPLE.xls"


@pytest.mark.skipif(not RUTA_SAMPLE.exists(), reason="No hay archivo sample")
class TestXlsFallback:
    def test_leer_xls_devuelve_filas(self):
        filas = leer_xls(str(RUTA_SAMPLE))
        assert filas is not None
        assert len(filas) > 10

    def test_leer_xls_tiene_encabezados(self):
        filas = leer_xls(str(RUTA_SAMPLE))
        encabezado = filas[9]
        assert "ARTICULO" in encabezado[2] or "ARTÍCULO" in encabezado[2]
        assert "ALMACEN" in encabezado[9]
        assert "STOCK" in encabezado[13]

    def test_leer_xls_tiene_total_al_final(self):
        filas = leer_xls(str(RUTA_SAMPLE))
        ultima_fila = filas[-1]
        valores = [v for v in ultima_fila if v]
        assert any("TOTAL" in v.upper() for v in valores)


@pytest.mark.skipif(not RUTA_SAMPLE.exists(), reason="No hay archivo sample")
class TestParser:
    def test_parsear_devuelve_dict(self):
        resultado = parsear_stock_desde_xls(str(RUTA_SAMPLE))
        assert isinstance(resultado, dict)
        assert len(resultado) > 0

    def test_parsear_tiene_almacenes_esperados(self):
        resultado = parsear_stock_desde_xls(str(RUTA_SAMPLE))
        for alm in ("VES", "40", "118"):
            assert alm in resultado, f"Almacen {alm} no encontrado"

    def test_parsear_sku_tiene_datos(self):
        resultado = parsear_stock_desde_xls(str(RUTA_SAMPLE))
        sku_ejemplo = list(resultado["VES"].keys())[0]
        info = resultado["VES"][sku_ejemplo]
        assert "stock" in info
        assert "predespacho" in info
        assert "descripcion" in info
        assert info["stock"] >= 0
        assert info["predespacho"] >= 0

    def test_parsear_stock_no_negativo(self):
        resultado = parsear_stock_desde_xls(str(RUTA_SAMPLE))
        for almacen, productos in resultado.items():
            for sku, info in productos.items():
                assert info["stock"] >= 0, f"Stock negativo en {almacen}/{sku}"
                assert info["predespacho"] >= 0, f"Predespacho negativo en {almacen}/{sku}"

    def test_parsear_no_tiene_total_como_sku(self):
        resultado = parsear_stock_desde_xls(str(RUTA_SAMPLE))
        for almacen, productos in resultado.items():
            for sku in productos:
                assert sku.upper() not in ("TOTAL", "SUBTOTAL", "TOTAL GENERAL"), (
                    f"SKU '{sku}' es una fila de total en almacen {almacen}"
                )

    def test_parsear_skus_no_vacios(self):
        resultado = parsear_stock_desde_xls(str(RUTA_SAMPLE))
        for almacen, productos in resultado.items():
            for sku in productos:
                assert sku.strip(), f"SKU vacio en almacen {almacen}"
