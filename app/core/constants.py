from __future__ import annotations

COLUMNA_SKU: int = 1
COLUMNA_DESCRIPCION: int = 2
COLUMNA_ALMACEN: int = 9
COLUMNA_UM: int = 12
COLUMNA_STOCK: int = 13
COLUMNA_PREDESPACHO: int = 16

# Estas posiciones son solo el FALLBACK: el parser ubica las columnas por
# ancla (ver ANCLAS_COLUMNAS). El reporte S1 trae el encabezado visual en una
# fila variable, con celdas combinadas y el SKU en la columna anterior a
# 'ARTICULO'; leer por posicion fija convierte un cambio de columna en un
# stock mal atribuido sin un solo error.

# Anclas: texto del encabezado -> campo. El orden de los alias importa poco,
# pero el de las claves no: la fila se acepta cuando estan TODAS las
# obligatorias.
ANCLAS_COLUMNAS: dict[str, tuple[str, ...]] = {
    "descripcion": ("ARTICULO", "DESCRIPCION", "NOMBRE"),
    "almacen": ("ALMACEN",),
    "um": ("UM", "UNIDAD DE MEDIDA", "U.M."),
    "stock": ("STOCK",),
    "predespacho": ("PREDESPACHO", "COMPROMISO", "PEDIDO"),
    "disponible": ("DISPONIBLE",),
}

COLUMNAS_OBLIGATORIAS: tuple[str, ...] = (
    "descripcion",
    "almacen",
    "um",
    "stock",
    "predespacho",
)

# Cuantas filas se recorren buscando el encabezado. El reporte real lo tiene
# en la fila 10; 60 da margen a un preambulo mas largo sin leer media hoja.
MAX_FILAS_BUSQUEDA: int = 60

# Columnas donde aparecen los headers de categoria (LINEA, GRUPO, TIPO, FAMILIA)
# Reporte resumido: cols 3, 6, 8, 11
# Reporte completo (appweb): col 1
COLUMNA_CATEGORIA: int = 1

FILAS_METADATA: int = 10

PREFIJOS_CATEGORIA: tuple[str, ...] = ("LINEA:", "GRUPO:", "TIPO:", "FAMILIA:")

PALABRAS_TOTAL: tuple[str, ...] = ("TOTAL", "SUBTOTAL", "TOTAL GENERAL")
PALABRAS_SALTAR: tuple[str, ...] = (".", "ARTICULO")

USER_AGENT: str = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)

ENCABEZADOS_HTTP: dict[str, str] = {
    "User-Agent": USER_AGENT,
}

ALMACEN_PRINCIPAL: str = "VES"
ALMACENES_MKTD: set[str] = {"118"}
# S* (sucursales) se detectan por prefijo "S" y son mktd
# Todo lo demas es venta


# Mapa de unidades de medida a nombres descriptivos
UM_NOMBRES: dict[str, str] = {
    "UND": "UNIDAD",
    "UN": "UNIDAD",
    "U": "UNIDAD",
    "KGR": "KILOGRAMO",
    "KG": "KILOGRAMO",
    "GR": "GRAMO",
    "LIT": "LITRO",
    "LT": "LITRO",
    "MTR": "METRO",
    "MT": "METRO",
    "ROL": "ROLLO",
    "RLL": "ROLLO",
    "BLS": "BOLSAS",
    "BL": "BLISTER",
    "BST": "BLISTER",
    "DIS": "DISPLAY",
    "EST": "ESTUCHE",
    "PAQ": "PAQUETE",
    "CJ": "CAJA",
    "BX": "CAJA",
    "CJA": "CAJA",
    "CJT": "CAJITA",
    "PAR": "PAR",
    "SET": "JUEGO",
    "JGO": "JUEGO",
    "MLL": "MILLAR",
    "MIL": "MILLAR",
}


def obtener_nombre_um(codigo: str) -> str:
    if not codigo:
        return ""
    return UM_NOMBRES.get(codigo.strip().upper(), codigo.strip().upper())


def obtener_nombre_almacen(codigo: str, catalog_nombres: dict | None = None) -> str:
    """Obtiene el nombre descriptivo de un almacen.

    Prioridad:
    1. Mapa del catalogo maestro (metadata.almacenes.nombres)
    2. Default genérico por tipo
    """
    if catalog_nombres and codigo in catalog_nombres:
        nombre = catalog_nombres[codigo]
        return nombre if nombre else codigo

    # Defaults por defecto
    defaults = {
        "VES": "Centro Logistico",
        "40": "Productos Terminados",
        "92": "Productos Terminados B",
        "106": "Productos Terminados C",
        "121": "Inspeccion Calidad",
        "122": "Devoluciones",
        "129": "Producto Terminado D",
        "118": "Marketing",
    }
    if codigo in defaults:
        return defaults[codigo]
    if codigo.startswith("S"):
        num = codigo[1:]
        return f"Sucursal {num}"
    return codigo


# ── Categorias de negocio ─────────────────────────────────────────────
# Lineas explicitas asignadas a cada categoria.
# Para lineas no listadas, se usa PREFIJOS_CATEGORIA_AUTO para inferir.
# El orden de PREFIJOS_CATEGORIA_AUTO importa: el primer prefijo que
# coincida gana (se evaluan de mas especifico a menos especifico).
#
# ESTA TAXONOMIA DEBE SER IGUAL A LA DE g360-master-data
# (scripts/generar_catalogo_base.py -> CATEGORIA_POR_LINEA). El catalogo la
# publica en su metadata y ambos repos se validan cruzadamente con
# scripts/validar_taxonomia.py. Si divergen, /stock y /catalog clasifican el
# mismo SKU en categorias distintas.
#
# CE y CF (MANUALIDADES y SET) son lineas Crayola: REPRESENTADAS, no VINIFAN.
# Lo mismo para las lineas propias de cada sub-marca Crayola (CA/CB/CC/CD).

CATEGORIAS: dict[str, list[str]] = {
    "VINIBALL": ["01", "MA", "14", "AD"],
    "VINIFAN": [
        "02",
        "09",
        "11",
        "72",
        "73",
        "75",
        "76",
        "77",
        "78",
        "79",
    ],
    "INDUMENTARIA": ["57", "52"],
    "REPRESENTADAS": ["85", "CE", "CF", "CA", "CB", "CC", "CD", "CG"],
    "PUBLICIDAD": ["80", "81"],
    "OTROS": ["99"],
}

# Prefijos de linea para clasificacion automatica (formato normalizado: sin prefijo '01')
# (mas especifico primero, menos especifico despues)
# Misma lista que g360-master-data (PREFIJOS_CATEGORIA_AUTO).
PREFIJOS_CATEGORIA_AUTO: list[tuple[str, str]] = [
    ("20", "INDUSTRIAL"),
    ("21", "INDUSTRIAL"),
    ("22", "INDUSTRIAL"),
    ("23", "INDUSTRIAL"),
    ("30", "CIPTECH"),
    ("31", "CIPTECH"),
    ("32", "CIPTECH"),
    ("33", "CIPTECH"),
    ("34", "CIPTECH"),
    ("35", "CIPTECH"),
    ("36", "CIPTECH"),
    ("37", "CIPTECH"),
    ("38", "CIPTECH"),
    ("39", "CIPTECH"),
    ("40", "MATERIALES"),
    ("41", "MATERIALES"),
    ("50", "MATERIALES"),
    ("51", "MATERIALES"),
    ("52", "MATERIALES"),
    ("53", "MATERIALES"),
    ("54", "MATERIALES"),
    ("55", "MATERIALES"),
    ("60", "DESCARTE Y VARIOS"),
    ("65", "DESCARTE Y VARIOS"),
    ("98", "DESCARTE Y VARIOS"),
    ("70", "PRODUCCION"),
    ("99", "OTROS"),
]

CATEGORIA_DEFAULT: str = "OTROS"


def asignar_categoria(codigo_linea: str) -> str:
    """Retorna la categoria de negocio para un codigo de linea."""
    if not codigo_linea:
        return ""
    codigo = codigo_linea.split(" - ")[0].strip()
    for clave, cat in CATEGORIAS.items():
        if codigo in cat:
            return clave
    for prefijo, cat in PREFIJOS_CATEGORIA_AUTO:
        if codigo.startswith(prefijo):
            return cat
    return CATEGORIA_DEFAULT


# ── Semaforo de venta ─────────────────────────────────────────────────
# Las TRES categorias de negocio que se venden. Todo lo demás (MATERIALES,
# CIPTECH, INDUSTRIAL, PRODUCCION, DESCARTE Y VARIOS, OTROS...) queda en
# REVISION_VENTA: puede estar publicado en el catálogo (que es el allowlist
# real del API) pero necesita una revisión comercial antes de cotizarse.
# Misma regla que g360-master-data (generar_catalogo_base.categoria_venta).
CATEGORIAS_VENTA: tuple[str, ...] = ("VINIBALL", "VINIFAN", "REPRESENTADAS")
CATEGORIA_VENTA_REVISION: str = "REVISION_VENTA"


def categoria_venta(categoria: str) -> str:
    """VINIBALL/VINIFAN/REPRESENTADAS, o REVISION_VENTA para el resto."""
    cat = str(categoria or "").strip().upper()
    return cat if cat in CATEGORIAS_VENTA else CATEGORIA_VENTA_REVISION
