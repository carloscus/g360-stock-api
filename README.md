# G360 Stock API

API REST para el reporte de stock **S1** desde **appweb.cipsa.com.pe**. Descarga el archivo XLS del ERP, lo parsea y lo sirve como JSON estructurado por SKU y almacen, enriquecido con unidad de medida y jerarquia de categorias (LINEA / GRUPO / TIPO / FAMILIA).

## Arquitectura

```
appweb.cipsa.com.pe ──XLS──▶ g360-stock-api ──▶ data/stock_cache.json
                    ──XLS──▶                  ──▶ data/stock_cache_sucursales.json
                                 │
                            JSON responses
                         (GET /api/v1/stock*)
```

- **Sin base de datos.** Cache en disco con backup rotativo (`.bak`) y TTL configurable.
- **Dos fuentes.** General (VES, 40, 118...) y Sucursales (S1, S2, S3...) desde distintas URLs.
- **Horario laboral L–S 7:00–22:59.** Fuera de ese rango y domingos no se descarga, se sirve cache vencido.
- **Stale cache.** Si appweb falla, se sirve cache vencido sin reintentar hasta el proximo TTL.
- **Retry.** Reintenta 1 vez ante timeout de red.
- **Thread-safe.** Lock de descarga para evitar duplicados en concurrencia.
- **8 almacenes, 3000+ SKUs, 34 lineas de producto** en el reporte completo.

## Endpoints

| Metodo | Ruta | Descripcion |
|--------|------|-------------|
| `GET` | `/api/v1/health` | Estado del servicio y cache |
| `GET` | `/api/v1/stock` | Listar stock completo con filtros |
| `GET` | `/api/v1/stock/{sku}` | Detalle de un SKU con desglose por almacen |
| `GET` | `/api/v1/almacenes` | Lista de almacenes disponibles |
| `GET` | `/api/v1/lineas` | Lista de lineas de producto |
| `GET` | `/api/v1/categorias` | Lista de categorias de negocio con sus lineas |
| `POST` | `/api/v1/upload` | Subir archivo .xls manualmente |

### Filtros de GET /api/v1/stock

| Parametro | Tipo | Ejemplo | Descripcion |
|-----------|------|---------|-------------|
| `almacen` | string | `VES`, `40`, `118` | Filtrar por codigo de almacen |
| `search` | string | `CRACKCITO` | Buscar por SKU o descripcion |
| `linea` | string | `0101`, `PELOTAS`, `78` | Filtrar por linea (tolerante: `78` → `0178`) |
| `categoria` | string | `VINIBALL`, `VINIFAN` | Filtrar por categoria de negocio |
| `um` | string | `UND`, `KGR`, `BST` | Filtrar por unidad de medida |
| `fuente` | string | `general`, `sucursales`, `todas` | Fuente de datos (default: `general`) |
| `limit` | int | `100` | Maximo de items a retornar |
| `offset` | int | `100` | Paginacion |

### Tolerancia de entrada

| Input | Resuelve | Ejemplo |
|-------|----------|---------|
| Linea `78` | `0178 - ARCHIVO` | padding a 4 digitos + match por prefijo |
| Linea `80` | `0180 - PUBLICIDAD` | idem |
| Linea `PELOTAS` | `0101 - PELOTAS` | busqueda por texto libre |
| SKU parcial | match en SKU y descripcion | via `?search=` |

## Cache

Dos archivos de cache en `data/`:
- `stock_cache.json` — fuente general
- `stock_cache_sucursales.json` — fuente sucursales

Cada uno con backup rotativo (`.bak`) que se activa si el principal se corrompe.

### Reglas de refresco

1. **Sin cache** → descarga forzada (sin importar dia/hora)
2. **Cache vigente** → sirve del cache
3. **Cache vencido + horario valido** (L–S 7:00–22:59) → descarga fresh
4. **Cache vencido + horario invalido** → sirve cache vencido
5. **Descarga falla + hay cache** → sirve cache vencido, reintenta en ~15 min

## Ejemplo de respuesta

```
GET /api/v1/stock?categoria=VINIBALL&limit=1
```

```json
{
  "metadata": {
    "fuente": "General (VES, 40, 118...)",
    "fecha_descarga": "2026-07-30T18:32:00Z",
    "total_skus": 312,
    "total_almacenes": 8,
    "cache_expirado": false,
    "cache_expiro_en": 900
  },
  "items": [
    {
      "sku": "011019",
      "descripcion": "N SEMIDEPORTIVA FUTBOL CRACKCITO BLANCO C/ROJO",
      "um": "UND",
      "linea": "0101 - PELOTAS",
      "grupo": "01 - NACIONAL",
      "tipo": "02 - SEMI-DEPORTIVA",
      "familia": "01 - FUTBOL",
      "categoria": "VINIBALL",
      "almacenes": [
        { "almacen": "VES", "tipo": "venta", "disponible": 6672, "stock": 7212, "predespacho": 540 },
        { "almacen": "118", "tipo": "informativo", "disponible": 4, "stock": 4, "predespacho": 0 },
        { "almacen": "40", "tipo": "venta", "disponible": 36, "stock": 36, "predespacho": 0 }
      ]
    }
  ]
}
```

## Categorias de negocio

| Categoria | Lineas |
|-----------|--------|
| VINIBALL | 0101 (PELOTAS), 01MA (MASCOTAS), 0114 (OTROS), 01AD (ACC. DEPORTIVOS) |
| VINIFAN | 0102, 0109, 0111, 0172–0179, 01CE, 01CF |
| INDUSTRIAL | 0120, 0121, 0123 |
| CIPTECH | 0130, 0131, 0133, 0135 |
| MATERIALES | 0140, 0150 |
| INDUMENTARIA | 0152, 0157 |
| PUBLICIDAD | 0180, 0181 |
| REPRESENTADAS | 0185 |
| PRODUCCION | 0170 |
| DESCARTE Y VARIOS | 0160, 0165, 0198 |
| OTROS | default |

## Estructura del proyecto

```
g360-stock-api/
├── app/
│   ├── core/
│   │   ├── constants.py      # Mapeo de columnas, categorias, prefijos
│   │   ├── parsers.py         # Parser dual (completo + resumen) con categorias, UM, lineas alfanumericas
│   │   └── xls_fallback.py    # Lector XLS multiformato
│   ├── models/
│   │   └── schemas.py         # Pydantic models: ItemStock, StockResponse, etc.
│   ├── routers/
│   │   ├── health.py          # GET /api/v1/health
│   │   ├── stock.py           # GET /api/v1/stock, /{sku}, /lineas, /almacenes, /categorias
│   │   ├── upload.py          # POST /api/v1/upload
│   │   └── resumen.py         # GET /api/v1/resumen
│   ├── services/
│   │   └── s1_service.py      # Logica de negocio: descarga, parseo, cache dual, filtros, horario, retry
│   ├── config.py              # Settings via pydantic-settings (2 fuentes, 2 caches, TTL, horario)
│   └── main.py                # FastAPI app con CORS y routers
├── tests/
│   ├── samples/               # REPT_STOCK_SAMPLE.xls (431 filas, 5 almacenes)
│   ├── test_api.py            # Tests de integracion
│   └── test_parsers.py        # Tests de parser
├── data/                      # Cache JSON + .bak (gitignored)
├── stock_cipsa.yaml           # Blueprint Render
├── requirements.txt
├── .env.example
└── .gitignore
```

## Configuracion

Variables de entorno (prefix `S1_`):

| Variable | Default | Descripcion |
|----------|---------|-------------|
| `S1_SOURCE1_URL` | URL appweb | Fuente general (parametroX2="") |
| `S1_SOURCE2_URL` | URL appweb | Fuente sucursales (parametroX2=1) |
| `S1_CACHE_TTL_SEGUNDOS` | `900` | TTL del cache en segundos (15 min) |
| `S1_CACHE_RUTA` | `data/stock_cache.json` | Cache de fuente general |
| `S1_CACHE_RUTA2` | `data/stock_cache_sucursales.json` | Cache de fuente sucursales |
| `S1_PUERTO` | `8000` | Puerto del servidor |

## Desarrollo

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Documentacion interactiva en `http://localhost:8000/docs`.

## Tests

```bash
pytest tests/ -v
```

22 tests que cubren:
- Parseo de XLS (formato resumen y completo, con lineas alfanumericas)
- Filtros por almacen, busqueda, linea, UM, categoria
- Calculo de disponible (stock - predespacho, nunca negativo)
- Cache, backup .bak, upload y fallback
- 404, health, almacenes, lineas, categorias

## Deploy en Render

El repositorio incluye `stock_cipsa.yaml` (Blueprints). Pasos:

1. Crear repositorio en GitHub y subir el proyecto
2. Render Dashboard → New → Blueprint → seleccionar repositorio
3. Render detecta `stock_cipsa.yaml` y configura automaticamente
4. Opcional: ajustar variables de entorno en Render Dashboard

Servicio desplegado en: `https://g360-stock-api.onrender.com`

## Licencia

Proyecto interno del ecosistema **G360 - CIPSA**.
