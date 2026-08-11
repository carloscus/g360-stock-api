from __future__ import annotations

import csv
import io
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional


def leer_xls(path: str) -> Optional[list[list[str]]]:
    """Lee un archivo XLS/XLSX/CVS/HTML/XML y retorna sus filas como lista de listas de strings.
    Intenta varios motores de parseo en orden; el primero que devuelva datos gana.
    """
    path_obj = Path(path)
    if not path_obj.exists():
        return None

    raw = path_obj.read_bytes()

    # Motores en orden de preferencia: xlsx -> xls -> csv -> html -> xml
    motores = [
        ("openpyxl", lambda: _leer_con_openpyxl(raw)),
        ("xlrd", lambda: _leer_con_xlrd(raw)),
        ("csv", lambda: _leer_con_csv(raw)),
        ("html", lambda: _leer_con_html(raw)),
        ("xml_spreadsheet", lambda: _leer_con_xml_spreadsheet(raw)),
    ]

    ultimo_error = None
    for nombre, fn in motores:
        try:
            resultado = fn()
            if resultado and len(resultado) > 1:
                return resultado
        except Exception as e:
            ultimo_error = e
            continue

    raise RuntimeError(
        f"No se pudo leer el archivo: {path}. "
        f"Ultimo error: {ultimo_error}"
    )


def _leer_con_openpyxl(raw: bytes) -> Optional[list[list[str]]]:
    """Parsea archivos .xlsx usando openpyxl (lectura solo)."""
    import openpyxl

    libro = openpyxl.load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
    hoja = libro.active
    filas = []
    for fila in hoja.iter_rows(values_only=True):
        filas.append([str(c).strip() if c is not None else "" for c in fila])
    libro.close()
    return filas


def _leer_con_xlrd(raw: bytes) -> Optional[list[list[str]]]:
    """Parsea archivos .xls usando xlrd."""
    import xlrd

    libro = xlrd.open_workbook(file_contents=raw)
    hoja = libro.sheet_by_index(0)
    filas = []
    for idx_fila in range(hoja.nrows):
        filas.append(
            [str(hoja.cell_value(idx_fila, c)).strip() for c in range(hoja.ncols)]
        )
    return filas


def _leer_con_csv(raw: bytes) -> Optional[list[list[str]]]:
    """Parsea archivos CSV (con deteccion automatica de BOM UTF-8)."""
    contenido = raw.decode("utf-8-sig", errors="replace")
    lector = csv.reader(io.StringIO(contenido))
    return [fila for fila in lector]


def _leer_con_html(raw: bytes) -> Optional[list[list[str]]]:
    """Parsea tablas HTML embebidas (formato que usa appweb.cipsa.com.pe)."""
    from bs4 import BeautifulSoup

    contenido = raw.decode("utf-8", errors="replace")
    sopa = BeautifulSoup(contenido, "html.parser")
    tabla = sopa.find("table")
    if not tabla:
        return None
    filas = []
    for tr in tabla.find_all("tr"):
        celdas = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
        if celdas:
            filas.append(celdas)
    return filas


def _leer_con_xml_spreadsheet(raw: bytes) -> Optional[list[list[str]]]:
    """Parsea archivos XML de spreadsheet (formato antiguo de Excel)."""
    ESPACIOS = {
        "ss": "urn:schemas-microsoft-com:office:spreadsheet",
        "o": "urn:schemas-microsoft-com:office:office",
        "x": "urn:schemas-microsoft-com:office:excel",
    }
    raiz = ET.fromstring(raw)
    worksheet = raiz.find(".//ss:Worksheet", ESPACIOS)
    if worksheet is None:
        worksheet = raiz.find(".//Worksheet")
    if worksheet is None:
        return None

    tabla = worksheet.find(".//ss:Table", ESPACIOS) or worksheet.find(".//Table")
    if tabla is None:
        return None

    filas = []
    for fila in tabla.findall(".//ss:Row", ESPACIOS) or tabla.findall("Row"):
        celdas = []
        for celda in fila.findall(".//ss:Cell", ESPACIOS) or fila.findall("Cell"):
            dato = celda.find(".//ss:Data", ESPACIOS) or celda.find("Data")
            texto = dato.text.strip() if dato is not None and dato.text else ""
            celdas.append(texto)
        if celdas:
            filas.append(celdas)
    return filas
