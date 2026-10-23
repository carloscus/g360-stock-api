from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import dataclass

from app.core.constants import (
    ANCLAS_COLUMNAS,
    COLUMNAS_OBLIGATORIAS,
    COLUMNA_ALMACEN,
    COLUMNA_CATEGORIA,
    COLUMNA_DESCRIPCION,
    COLUMNA_PREDESPACHO,
    COLUMNA_SKU,
    COLUMNA_STOCK,
    COLUMNA_UM,
    FILAS_METADATA,
    MAX_FILAS_BUSQUEDA,
    PALABRAS_SALTAR,
    PALABRAS_TOTAL,
    PREFIJOS_CATEGORIA,
)
from app.core.xls_fallback import leer_xls

logger = logging.getLogger(__name__)

PATRON_CATEGORIA = re.compile(
    r"^(LINEA|GRUPO|TIPO|FAMILIA):\s*([\dA-Za-z]+)(?:\s*-\s*(.+))?$"
)
PATRON_SKU = re.compile(r"^[0-9A-Z]{5,8}$")


@dataclass(frozen=True)
class ColumnasReporte:
    """Ubicacion de cada campo dentro del reporte S1."""

    fila_datos: int
    sku: int
    descripcion: int
    almacen: int
    um: int
    stock: int
    predespacho: int
    detectado: bool = True

    @property
    def ancho_minimo(self) -> int:
        return (
            max(
                self.sku,
                self.descripcion,
                self.almacen,
                self.um,
                self.stock,
                self.predespacho,
            )
            + 1
        )


# Layout historico: solo se usa si las anclas no aparecen (reporte distinto o
# encabezado partido). En ese caso se avisa en el log.
COLUMNAS_POR_DEFECTO = ColumnasReporte(
    fila_datos=FILAS_METADATA,
    sku=COLUMNA_SKU,
    descripcion=COLUMNA_DESCRIPCION,
    almacen=COLUMNA_ALMACEN,
    um=COLUMNA_UM,
    stock=COLUMNA_STOCK,
    predespacho=COLUMNA_PREDESPACHO,
    detectado=False,
)


def _normalizar(valor) -> str:
    """Encabezado comparable: sin acentos, NBSP/BOM, espacios de mas ni caja."""
    texto = str(valor or "").replace("\ufeff", "").replace("\xa0", " ")
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return " ".join(texto.split()).strip().upper()


def _parece_sku(valor) -> bool:
    texto = str(valor or "").strip().lstrip("'").upper()
    if texto.endswith(".0"):
        texto = texto[:-2]
    if not texto or texto in PALABRAS_SALTAR or texto in PALABRAS_TOTAL:
        return False
    return bool(PATRON_SKU.match(texto))


def _buscar_columna_sku(filas_datos: list[list], idx_desc: int) -> int | None:
    """Columna con mas celdas con forma de SKU, priorizando la de la descripcion."""
    ancho = max((len(f) for f in filas_datos), default=0)
    mejor: tuple[int, int] | None = None
    elegido: int | None = None
    for col in range(ancho):
        if col == idx_desc:
            continue
        aciertos = sum(
            1 for fila in filas_datos if col < len(fila) and _parece_sku(fila[col])
        )
        if not aciertos:
            continue
        candidato = (aciertos, -abs(col - (idx_desc - 1)))
        if mejor is None or candidato > mejor:
            mejor = candidato
            elegido = col
    return elegido


def detectar_columnas(filas: list[list]) -> ColumnasReporte | None:
    """Ubica la fila de encabezado y las columnas por ancla.

    Devuelve None si no encuentra el encabezado: el llamador decide si cae al
    layout historico (con aviso) o falla.
    """
    limite = min(len(filas), MAX_FILAS_BUSQUEDA)
    for r in range(limite):
        normalizados = [_normalizar(c) for c in filas[r]]
        indices: dict[str, int] = {}
        for campo, alias in ANCLAS_COLUMNAS.items():
            for a in alias:
                buscado = _normalizar(a)
                if buscado in normalizados:
                    indices[campo] = normalizados.index(buscado)
                    break
        if not all(c in indices for c in COLUMNAS_OBLIGATORIAS):
            continue

        idx_desc = indices["descripcion"]
        idx_sku = idx_desc - 1 if idx_desc > 0 else -1
        muestra = filas[r + 1 : r + 11]
        if idx_sku < 0 or not any(
            _parece_sku(fila[idx_sku]) for fila in muestra if len(fila) > idx_sku
        ):
            alternativo = _buscar_columna_sku(muestra, idx_desc)
            if alternativo is None:
                logger.warning(
                    "S1: encabezado en fila %d pero no encuentro la columna SKU "
                    "(ni la anterior a ARTICULO ni por contenido)",
                    r + 1,
                )
                return None
            logger.warning(
                "S1: la columna SKU no es 'descripcion - 1'; se detecto la "
                "columna %d por contenido",
                alternativo + 1,
            )
            idx_sku = alternativo

        columnas = ColumnasReporte(
            fila_datos=r + 1,
            sku=idx_sku,
            descripcion=idx_desc,
            almacen=indices["almacen"],
            um=indices["um"],
            stock=indices["stock"],
            predespacho=indices["predespacho"],
        )
        logger.info(
            "S1: encabezado fila %d; sku=%d desc=%d almacen=%d um=%d stock=%d pred=%d",
            r + 1,
            columnas.sku,
            columnas.descripcion,
            columnas.almacen,
            columnas.um,
            columnas.stock,
            columnas.predespacho,
        )
        return columnas
    return None


def detectar_columna_categoria(filas: list[list]) -> int | None:
    """Columna donde viven las filas 'LINEA: 0101' / 'GRUPO: ...'.

    No siempre es la misma: el reporte resumido y el completo las ponen en
    columnas distintas. Buscarla evita perder toda la taxonomia en silencio
    (linea/grupo/tipo/familia vacios, y con eso el catalogo de los SKU que
    solo existen en S1).
    """
    for fila in filas[:MAX_FILAS_BUSQUEDA]:
        for i, valor in enumerate(fila):
            if _es_fila_categoria(str(valor or "").strip()):
                return i
    return None


def parsear_stock_desde_xls(
    ruta: str,
) -> dict[str, dict[str, dict]]:
    filas = leer_xls(ruta)
    if not filas:
        return {}

    columnas = detectar_columnas(filas)
    if columnas is None:
        columnas = COLUMNAS_POR_DEFECTO
        logger.warning(
            "S1: no pude ubicar el encabezado por anclas; uso el layout "
            "posicional historico (sku=%d, almacen=%d, stock=%d). Revisar el "
            "reporte: si cambio de formato, el stock puede estar mal atribuido.",
            columnas.sku + 1,
            columnas.almacen + 1,
            columnas.stock + 1,
        )

    col_categoria = detectar_columna_categoria(filas)
    if col_categoria is None:
        col_categoria = COLUMNA_CATEGORIA

    resultado: dict[str, dict[str, dict]] = {}
    ultimo_sku = ""
    ultima_desc = ""

    linea_actual = ""
    grupo_actual = ""
    tipo_actual = ""
    familia_actual = ""
    um_actual = ""

    tiene_categorias = _detectar_formato_con_categorias(filas, col_categoria)

    # Pre-scan ALL rows for category headers before data rows start
    if tiene_categorias:
        for fila in filas:
            if len(fila) > col_categoria:
                cell = str(fila[col_categoria] or "").strip()
                if _es_fila_categoria(cell):
                    linea_actual, grupo_actual, tipo_actual, familia_actual = (
                        _extraer_categorias(
                            cell,
                            linea_actual,
                            grupo_actual,
                            tipo_actual,
                            familia_actual,
                        )
                    )

    ancho = columnas.ancho_minimo
    for fila in filas[columnas.fila_datos :]:
        if len(fila) < ancho:
            continue

        # Check categoria column in this row for header rows
        if tiene_categorias and len(fila) > col_categoria:
            cell = str(fila[col_categoria] or "").strip()
            if _es_fila_categoria(cell):
                linea_actual, grupo_actual, tipo_actual, familia_actual = (
                    _extraer_categorias(
                        cell, linea_actual, grupo_actual, tipo_actual, familia_actual
                    )
                )

        raw_sku = str(fila[columnas.sku] or "").strip().lstrip("'")
        sku_mayus = raw_sku.upper()

        if sku_mayus in PALABRAS_TOTAL:
            ultimo_sku = ""
            continue

        if raw_sku and sku_mayus not in PALABRAS_SALTAR:
            ultimo_sku = raw_sku
            ultima_desc = str(fila[columnas.descripcion] or "").strip()

        if not ultimo_sku:
            continue

        almacen = str(fila[columnas.almacen] or "").strip().upper()
        if not almacen:
            continue

        um_actual = str(fila[columnas.um] or "").strip()

        stock_crudo = str(fila[columnas.stock] or "0").strip()
        pred_crudo = str(fila[columnas.predespacho] or "0").strip()

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


def _detectar_formato_con_categorias(filas: list[list], col: int) -> bool:
    for fila in filas:
        if len(fila) <= col:
            continue
        texto = str(fila[col] or "").strip().upper()
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
