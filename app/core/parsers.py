from __future__ import annotations

import re

from app.core.constants import (
    COLUMNA_SKU,
    COLUMNA_DESCRIPCION,
    COLUMNA_ALMACEN,
    COLUMNA_UM,
    COLUMNA_STOCK,
    COLUMNA_PREDESPACHO,
    FILAS_METADATA,
    COLUMNA_CATEGORIA,
    PREFIJOS_CATEGORIA,
    PALABRAS_TOTAL,
    PALABRAS_SALTAR,
)
from app.core.xls_fallback import leer_xls

PATRON_CATEGORIA = re.compile(r"^(LINEA|GRUPO|TIPO|FAMILIA):\s*([\dA-Za-z]+)(?:\s*-\s*(.+))?$")


def parsear_stock_desde_xls(
    ruta: str,
) -> dict[str, dict[str, dict]]:
    filas = leer_xls(ruta)
    if not filas:
        return {}

    resultado: dict[str, dict[str, dict]] = {}
    ultimo_sku = ""
    ultima_desc = ""

    linea_actual = ""
    grupo_actual = ""
    tipo_actual = ""
    familia_actual = ""
    um_actual = ""

    tiene_categorias = _detectar_formato_con_categorias(filas)

    # Pre-scan ALL rows for category headers before data rows start
    if tiene_categorias:
        for fila in filas:
            if len(fila) > COLUMNA_CATEGORIA:
                cell = str(fila[COLUMNA_CATEGORIA] or "").strip()
                if _es_fila_categoria(cell):
                    linea_actual, grupo_actual, tipo_actual, familia_actual = (
                        _extraer_categorias(cell, linea_actual, grupo_actual, tipo_actual, familia_actual)
                    )

    for fila in filas[FILAS_METADATA:]:
        if len(fila) < 17:
            continue

        # Check categoria column in this row for header rows
        if tiene_categorias and len(fila) > COLUMNA_CATEGORIA:
            cell = str(fila[COLUMNA_CATEGORIA] or "").strip()
            if _es_fila_categoria(cell):
                linea_actual, grupo_actual, tipo_actual, familia_actual = (
                    _extraer_categorias(cell, linea_actual, grupo_actual, tipo_actual, familia_actual)
                )

        raw_sku = str(fila[COLUMNA_SKU] or "").strip().lstrip("'")
        sku_mayus = raw_sku.upper()

        if sku_mayus in PALABRAS_TOTAL:
            ultimo_sku = ""
            continue

        if raw_sku and sku_mayus not in PALABRAS_SALTAR:
            ultimo_sku = raw_sku
            ultima_desc = str(fila[COLUMNA_DESCRIPCION] or "").strip()

        if not ultimo_sku:
            continue

        almacen = str(fila[COLUMNA_ALMACEN] or "").strip().upper()
        if not almacen:
            continue

        um_actual = str(fila[COLUMNA_UM] or "").strip()

        stock_crudo = str(fila[COLUMNA_STOCK] or "0").strip()
        pred_crudo = str(fila[COLUMNA_PREDESPACHO] or "0").strip()

        try:
            stock = int(float(stock_crudo.replace(",", "")))
            predespacho = int(float(pred_crudo.replace(",", ""))) if pred_crudo else 0
        except (ValueError, TypeError, AttributeError):
            continue

        almacen_datos = resultado.setdefault(almacen, {})
        if ultimo_sku not in almacen_datos:
            almacen_datos[ultimo_sku] = {
                "stock": 0,
                "predespacho": 0,
                "descripcion": ultima_desc,
                "um": um_actual,
                "linea": linea_actual,
                "grupo": grupo_actual,
                "tipo": tipo_actual,
                "familia": familia_actual,
            }
        almacen_datos[ultimo_sku]["stock"] += stock
        almacen_datos[ultimo_sku]["predespacho"] += predespacho

        if um_actual and not almacen_datos[ultimo_sku].get("um"):
            almacen_datos[ultimo_sku]["um"] = um_actual

    return resultado


def _detectar_formato_con_categorias(filas: list[list[str]]) -> bool:
    for fila in filas:
        if len(fila) <= COLUMNA_CATEGORIA:
            continue
        texto = str(fila[COLUMNA_CATEGORIA] or "").strip().upper()
        if any(texto.startswith(p) for p in PREFIJOS_CATEGORIA):
            return True
    return False


def _es_fila_categoria(texto: str) -> bool:
    if not texto:
        return False
    return any(texto.upper().startswith(p) for p in PREFIJOS_CATEGORIA)


def _extraer_categorias(
    texto: str,
    linea_actual: str,
    grupo_actual: str,
    tipo_actual: str,
    familia_actual: str,
) -> tuple[str, str, str, str]:
    coincide = PATRON_CATEGORIA.match(texto)
    if not coincide:
        return linea_actual, grupo_actual, tipo_actual, familia_actual

    nivel = coincide.group(1).upper()
    codigo = coincide.group(2).strip()
    nombre = (coincide.group(3) or "").strip()

    # Skip placeholder values like "TODOS"
    if nombre.upper() == "TODOS":
        nombre = ""

    if nivel == "LINEA":
        valor = f"{codigo} - {nombre}" if nombre else codigo
        return valor, "", "", ""
    elif nivel == "GRUPO":
        valor = f"{codigo} - {nombre}" if nombre else codigo
        return linea_actual, valor, "", ""
    elif nivel == "TIPO":
        valor = f"{codigo} - {nombre}" if nombre else codigo
        return linea_actual, grupo_actual, valor, ""
    elif nivel == "FAMILIA":
        valor = f"{codigo} - {nombre}" if nombre else codigo
        return linea_actual, grupo_actual, tipo_actual, valor

    return linea_actual, grupo_actual, tipo_actual, familia_actual
