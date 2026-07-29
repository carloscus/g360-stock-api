# G360 Stock API

API REST para el reporte de stock **S1** desde **appweb.cipsa.com.pe**. Descarga el archivo XLS del ERP, lo parsea y lo sirve como JSON estructurado por SKU y almacen, enriquecido con unidad de medida y jerarquia de categorias (LINEA / GRUPO / TIPO / FAMILIA).

## Arquitectura

```
appweb.cipsa.com.pe ──XLS──▶ g360-stock-api ──▶ data/stock_cache.json
                                │
                           JSON responses
                        (GET /api/v1/stock*)
```

- **Sin base de datos.** Todo el estado vive en un archivo JSON en disco con TTL 1h.
- **Stale cache.** Si appweb falla, se sirve cache vencido con header `X-Stale: true`.
- **8 almacenes, 2178+ SKUs, 30 lineas de producto** en el reporte completo.

## Endpoints

| Metodo | Ruta | Descripcion |
|--------|------|-------------|
| `GET` | `/api/v1/health` | Estado del servicio y cache |
| `GET` | `/api/v1/stock` | Listar stock completo con filtros |
| `GET` | `/api/v1/stock/{sku}` | Detalle de un SKU con desglose por almacen |
| `GET` | `/api/v1/almacenes` | Lista de almacenes disponibles |
| `GET` | `/api/v1/lineas` | Lista de lineas de producto (solo formato completo) |
| `GET` | `/api/v1/resumen` | KPIs: total SKU, con/sin stock, predespachados |
| `POST` | `/api/v1/upload` | Subir archivo .xls manualmente |

### Filtros de GET /api/v1/stock

| Parametro | Tipo | Ejemplo | Descripcion |
|-----------|------|---------|-------------|
| `almacen` | string | `VES`, `40`, `118` | Filtrar por codigo de almacen |
| `search` | string | `CRACKCITO` | Buscar por SKU o descripcion |
| `linea` | string | `0101`, `PELOTAS` | Filtrar por linea de producto |
| `um` | string | `UND`, `KGR`, `BST` | Filtrar por unidad de medida |

## Ejemplo de respuesta

```
GET /api/v1/stock
```

```json
{
  "metadata": {
    "fuente": "http://appweb.cipsa.com.pe:8054/...",
    "fecha_descarga": "2026-07-29T08:21:33",
    "total_skus": 2178,
    "total_almacenes": 8,
    "cache_expirado": false,
    "cache_expiro_en": 3600
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
      "almacenes": [
        { "almacen": "VES", "disponible": 6672, "stock": 7212, "predespacho": 540 },
        { "almacen": "118", "disponible": 4,    "stock": 4,    "predespacho": 0 },
        { "almacen": "121", "disponible": 3,    "stock": 3,    "predespacho": 0 },
        { "almacen": "40",  "disponible": 36,   "stock": 36,   "predespacho": 0 }
      ]
    }
  ]
}
```

```
GET /api/v1/stock/85286
```

```json
{
  "sku": "85286",
  "descripcion": "ENGRAPADOR ALICATE ECO 26/6 Y 24/6",
  "um": "UND",
  "linea": "0185 - REPRESENTADAS",
  "grupo": "06 - RAPID",
  "tipo": "01 - ENGRAPADOR",
  "familia": "01 - ENGRAPADOR",
  "almacenes": [
    { "almacen": "VES", "disponible": 0,  "stock": 20, "predespacho": 20 },
    { "almacen": "118", "disponible": 11, "stock": 11, "predespacho": 0 }
  ]
}
```

## Cache

El servicio mantiene un cache en `data/stock_cache.json` con TTL configurable mediante `S1_CACHE_TTL_SEGUNDOS` (default: **3600s = 1h**).

- **Cache valido:** responde datos frescos desde appweb.
- **Cache vencido (stale):** si appweb falla, se sirven datos viejos con header `X-Stale: true`.
- **POST /api/v1/upload:** reemplaza el cache manualmente subiendo un XLS.

## Estructura del proyecto

```
g360-stock-api/
├── app/
│   ├── core/
│   │   ├── constants.py      # Mapeo de columnas, palabras reservadas
│   │   ├── parsers.py         # Parser dual (completo + resumen) con categorias y UM
│   │   └── xls_fallback.py    # Lector XLS multiformato
│   ├── models/
│   │   └── schemas.py         # Pydantic models: ItemStock, StockResponse, etc.
│   ├── routers/
│   │   ├── health.py          # GET /api/v1/health
│   │   ├── stock.py           # GET /api/v1/stock, /lineas, /almacenes
│   │   ├── upload.py          # POST /api/v1/upload
│   │   └── resumen.py         # GET /api/v1/resumen
│   ├── services/
│   │   └── s1_service.py      # Logica de negocio: descarga, parseo, cache, filtros
│   ├── config.py              # Settings via pydantic-settings (env vars + defaults)
│   └── main.py                # FastAPI app con CORS y routers
├── tests/
│   ├── samples/               # REPT_STOCK_SAMPLE.xls (431 filas, 5 almacenes)
│   ├── test_api.py            # 13 tests de integracion
│   └── test_parsers.py        # 9 tests de parser
├── data/                      # Cache JSON (gitignored)
├── stock_cipsa.yaml           # Blueprint Render
├── requirements.txt
├── .env.example
└── .gitignore
```

## Configuracion

Variables de entorno (prefix `S1_`):

| Variable | Default | Descripcion |
|----------|---------|-------------|
| `S1_SOURCE1_URL` | URL appweb completo | URL del reporte S1 en appweb.cipsa.com.pe |
| `S1_CACHE_TTL_SEGUNDOS` | `3600` | TTL del cache en segundos |
| `S1_CACHE_RUTA` | `data/stock_cache.json` | Ruta del archivo de cache |

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

22 tests (13 API + 9 parser) que cubren:
- Parseo de XLS (formato resumen y completo)
- Filtros por almacen, busqueda, linea, UM
- Calculo de disponible (stock - predespacho, nunca negativo)
- Cache, upload y stale fallback

## Deploy en Render

El repositorio incluye `stock_cipsa.yaml` (Blueprints). Pasos:

1. Crear repositorio en GitHub y subir el proyecto
2. Render Dashboard → New → Blueprint → seleccionar repositorio
3. Render detecta `stock_cipsa.yaml` y configura automaticamente
4. Opcional: ajustar variables de entorno en Render Dashboard

Servicio desplegado en: `https://g360-stock-api.onrender.com`

## Licencia

Proyecto interno del ecosistema **G360 - CIPSA**.
