from __future__ import annotations

COLUMNA_SKU: int = 1
COLUMNA_DESCRIPCION: int = 2
COLUMNA_ALMACEN: int = 9
COLUMNA_UM: int = 12
COLUMNA_STOCK: int = 13
COLUMNA_PREDESPACHO: int = 16

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

# ── Categorias de negocio ─────────────────────────────────────────────
# Lineas explicitas asignadas a cada categoria.
# Para lineas no listadas, se usa PREFIJOS_CATEGORIA_AUTO para inferir.
# El orden de PREFIJOS_CATEGORIA_AUTO importa: el primer prefijo que
# coincida gana (se evaluan de mas especifico a menos especifico).

CATEGORIAS: dict[str, list[str]] = {
    "VINIBALL": ["0101", "01MA", "0114", "01AD", "0181"],
    "VINIFAN": [
        "0102", "0109", "0111",
        "0172", "0173", "0175", "0176", "0177", "0178", "0179",
        "01CE", "01CF",
    ],
    "INDUMENTARIA": ["0157", "0152"],
    "REPRESENTADAS": ["0185"],
    "PUBLICIDAD": ["0180"],
}

# Prefijos de linea para clasificacion automatica
# (mas especifico primero, menos especifico despues)
PREFIJOS_CATEGORIA_AUTO: list[tuple[str, str]] = [
    ("0120", "INDUSTRIAL"),
    ("0121", "INDUSTRIAL"),
    ("0123", "INDUSTRIAL"),
    ("0130", "CIPTECH"),
    ("0131", "CIPTECH"),
    ("0133", "CIPTECH"),
    ("0135", "CIPTECH"),
    ("0140", "MATERIALES"),
    ("0150", "MATERIALES"),
    ("0160", "DESCARTE Y VARIOS"),
    ("0165", "DESCARTE Y VARIOS"),
    ("0170", "PRODUCCION"),
    ("0198", "DESCARTE Y VARIOS"),
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
