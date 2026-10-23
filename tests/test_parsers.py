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
        assert "ARTICULO" in encabezado[2] or "ARTÃCULO" in encabezado[2]
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
                assert info["predespacho"] >= 0, (
                    f"Predespacho negativo en {almacen}/{sku}"
                )

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


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Deteccion por anclas (sin sample: filas sinteticas)
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

from app.core import parsers as _parsers  # noqa: E402
from app.core.parsers import (  # noqa: E402
    COLUMNAS_POR_DEFECTO,
    detectar_columna_categoria,
    detectar_columnas,
)

ANCHO = 20


def _fila(ancho: int = ANCHO) -> list:
    return [""] * ancho


def _reporte(desplazamiento: int = 0, preambulo: int = 9) -> list[list]:
    """Reporte S1 sintetico: preambulo + encabezado + categorias + datos."""
    d = desplazamiento
    filas = [_fila() for _ in range(preambulo)]
    cabecera = _fila()
    cabecera[2 + d] = "ARTICULO"
    cabecera[9 + d] = "ALMACEN"
    cabecera[12 + d] = "UM"
    cabecera[13 + d] = "STOCK"
    cabecera[16 + d] = "PREDESPACHO"
    cabecera[18 + d] = "DISPONIBLE"
    filas.append(cabecera)
    for texto in (
        "LINEA: 0101 - PELOTAS",
        "GRUPO: 02 - FUTBOL",
        "TIPO: 05 - N5",
        "FAMILIA: 07 - BLANCO",
    ):
        fila = _fila()
        fila[1 + d] = texto
        filas.append(fila)
    for sku, desc, almacen, stock, pred in (
        ("016763", "PELOTA VINIBALL N5", "VES", 5, 2),
        ("016763", "PELOTA VINIBALL N5", "VES", 3, 1),
        ("016764", "PELOTA VINIFAN N3", "118", 7, 0),
    ):
        fila = _fila()
        fila[1 + d] = sku
        fila[2 + d] = desc
        fila[9 + d] = almacen
        fila[12 + d] = "UND"
        fila[13 + d] = stock
        fila[16 + d] = pred
        filas.append(fila)
    total = _fila()
    total[1 + d] = "TOTAL"
    filas.append(total)
    return filas


def _parsear(monkeypatch, filas) -> dict:
    monkeypatch.setattr(_parsers, "leer_xls", lambda ruta: filas)
    return parsear_stock_desde_xls("sintetico.xls")


class TestDetectarColumnas:
    def test_encabezado_real(self):
        columnas = detectar_columnas(_reporte())
        assert columnas is not None
        assert columnas.fila_datos == 10
        assert columnas.sku == 1
        assert columnas.descripcion == 2
        assert columnas.almacen == 9
        assert columnas.um == 12
        assert columnas.stock == 13
        assert columnas.predespacho == 16
        assert columnas.detectado is True

    def test_preambulo_mas_largo(self):
        columnas = detectar_columnas(_reporte(preambulo=25))
        assert columnas is not None
        assert columnas.fila_datos == 26

    def test_columnas_desplazadas(self):
        columnas = detectar_columnas(_reporte(desplazamiento=1))
        assert columnas is not None
        assert columnas.sku == 2
        assert columnas.almacen == 10
        assert columnas.stock == 14

    def test_sin_encabezado_devuelve_none(self):
        assert detectar_columnas([_fila() for _ in range(15)]) is None

    def test_falta_ancla_devuelve_none(self):
        filas = _reporte()
        filas[9][16] = ""
        assert detectar_columnas(filas) is None

    def test_sku_fuera_de_descripcion_menos_uno(self):
        filas = _reporte()
        # El SKU vive en la columna 0 y la 1 queda vacia.
        for fila in filas[10:]:
            if len(fila) > 1 and "PELOTA" in str(fila[2]):
                fila[0] = fila[1]
                fila[1] = ""
        columnas = detectar_columnas(filas)
        assert columnas is not None
        assert columnas.sku == 0

    def test_defecto_es_el_layout_historico(self):
        assert COLUMNAS_POR_DEFECTO.sku == 1
        assert COLUMNAS_POR_DEFECTO.stock == 13
        assert COLUMNAS_POR_DEFECTO.detectado is False


class TestDetectarColumnaCategoria:
    def test_categoria_en_columna_1(self):
        assert detectar_columna_categoria(_reporte()) == 1

    def test_categoria_desplazada(self):
        assert detectar_columna_categoria(_reporte(desplazamiento=1)) == 2

    def test_fila_de_filtros_no_distrae(self):
        # El reporte real mezcla una fila de filtros (LINEA/GRUPO/TODO en una
        # sola fila, en otra columna) con los encabezados de verdad (uno por
        # fila, repetidos por grupo). Gana la columna con mas filas.
        filas = _reporte()
        filtro = _fila()
        filtro[3] = "LINEA: TODOS"
        filtro[6] = "GRUPO: TODOS"
        filas.insert(5, filtro)
        assert detectar_columna_categoria(filas) == 1

    def test_sin_categorias(self):
        prefijos = ("LINEA:", "GRUPO:", "TIPO:", "FAMILIA:")
        filas = [
            fila for fila in _reporte() if not str(fila[1]).upper().startswith(prefijos)
        ]
        assert detectar_columna_categoria(filas) is None


class TestParsearSintetico:
    def test_lee_stock_y_acumula(self, monkeypatch):
        resultado = _parsear(monkeypatch, _reporte())
        assert resultado["VES"]["016763"]["stock"] == 8
        assert resultado["VES"]["016763"]["predespacho"] == 3
        assert resultado["118"]["016764"]["stock"] == 7

    def test_lee_categorias(self, monkeypatch):
        resultado = _parsear(monkeypatch, _reporte())
        info = resultado["VES"]["016763"]
        assert info["linea"] == "0101 - PELOTAS"
        assert info["grupo"] == "02 - FUTBOL"
        assert info["tipo"] == "05 - N5"
        assert info["familia"] == "07 - BLANCO"
        assert info["um"] == "UND"

    def test_no_crea_sku_total(self, monkeypatch):
        resultado = _parsear(monkeypatch, _reporte())
        for productos in resultado.values():
            assert "TOTAL" not in {s.upper() for s in productos}

    def test_reporte_desplazado_da_el_mismo_resultado(self, monkeypatch):
        normal = _parsear(monkeypatch, _reporte())
        desplazado = _parsear(monkeypatch, _reporte(desplazamiento=1))
        assert normal == desplazado

    def test_sin_anclas_cae_al_layout_historico(self, monkeypatch):
        filas = _reporte()
        filas[9][16] = ""  # sin PREDESPACHO no hay anclas
        resultado = _parsear(monkeypatch, filas)
        # El layout historico igual lee: no rompe el servicio.
        assert resultado["VES"]["016763"]["stock"] == 8


class TestEnriquecerNoHaceEco:
    """El universo compacto debe llevar la ficha del S1, no el eco del
    catalogo. Caso real: un item S1-only entro una vez al catalogo con
    linea OTROS (fallback); al regenerar, el enriquecido repetia OTROS
    desde el catalogo y el OTROS no salia nunca (ni los D se enlazaban)."""

    def _item_s1(self):
        from app.models.schemas import AlmacenStock, ItemStock

        return ItemStock(
            sku="03077D",
            descripcion="FOLDER N VINIFAN TAPA",
            um="UND",
            linea="0198 - PRODUCTOS SIN EMBALAJE",
            grupo="06 - ARCHIVOS",
            tipo="TA - TAPA",
            familia="OF - OFICIO",
            categoria="",
            almacenes=[
                AlmacenStock(
                    almacen="VES", tipo="venta", disponible=7, stock=7, predespacho=0
                )
            ],
        )

    def _catalogo_echo(self):
        from app.services.catalog_service import catalog_service

        catalog_service._catalog = {
            "03077D": {
                "sku": "03077D",
                "origen": "s1",
                "linea": "OTROS",
                "linea_codigo": "",
                "linea_nombre": "OTROS",
                "categoria": "OTROS",
            }
        }
        return catalog_service

    def test_item_s1_conserva_linea_del_reporte(self, monkeypatch):
        from app.services.s1_service import ServicioStock

        catalog_service = self._catalogo_echo()
        try:
            servicio = ServicioStock.__new__(ServicioStock)
            resultado = servicio._enriquecer_items([self._item_s1()])
        finally:
            catalog_service._catalog = {}
            catalog_service._fecha_carga = None
        assert len(resultado) == 1
        assert resultado[0].linea == "0198 - PRODUCTOS SIN EMBALAJE"
        assert resultado[0].linea_id in ("98", "0198")

    def test_item_erp_sigue_mandando_catalogo(self):
        from app.services.s1_service import ServicioStock
        from app.models.schemas import AlmacenStock, ItemStock
        from app.services.catalog_service import catalog_service

        catalog_service._catalog = {
            "CA001": {
                "sku": "CA001",
                "origen": "erp",
                "linea": "CA",
                "linea_codigo": "CA",
                "linea_nombre": "PINTURA",
                "categoria": "REPRESENTADAS",
            }
        }
        try:
            servicio = ServicioStock.__new__(ServicioStock)
            item = ItemStock(
                sku="CA001",
                descripcion="PINTURA",
                um="UND",
                linea="77 - PINTURA",
                grupo="",
                tipo="",
                familia="",
                categoria="",
                almacenes=[
                    AlmacenStock(
                        almacen="VES",
                        tipo="venta",
                        disponible=1,
                        stock=1,
                        predespacho=0,
                    )
                ],
            )
            resultado = servicio._enriquecer_items([item])
        finally:
            catalog_service._catalog = {}
            catalog_service._fecha_carga = None
        # El catalogo ERP manda (desambiguacion Crayola): no regresion.
        assert resultado[0].linea_id == "CA"

