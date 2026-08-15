# g360-stock-api

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="logotypes/logo-g360-light.svg">
  <img alt="g360-stock-api" height="64" src="logotypes/logo-g360-dark.svg">
</picture>

> API REST para el reporte de stock **S1** desde **appweb.cipsa.com.pe**. Descarga los archivos XLS del ERP (general + sucursales), los parsea y los sirve como JSON estructurado por SKU y almacen, enriquecido con datos del catalogo maestro.

[![Version](https://img.shields.io/badge/version-1.1.0-blue)](https://github.com)
[![Skill](https://img.shields.io/badge/skill-cipsa-green)](https://github.com/carloscus/g360-cli)

## ¿Cómo está organizado el proyecto?

```
appweb.cipsa.com.pe ──XLS──▶ g360-stock-api ──▶ data/stock_cache.json
                    ──XLS──▶                  ──▶ data/stock_cache_sucursales.json
                     (general)                 (sucursales)
                                   │
                      g360-master-data ──JSON──▶ data/catalog_cache.json
                                   │
                              JSON responses
                           (GET /api/v1/stock*)
```

- **Sin base de datos.** Cache en disco con backup rotativo (`.bak`) y TTL configurable.
- **Dos fuentes de stock.** General (VES, 40, 118...) y Sucursales (S1, S2, S3...). Se mergean automaticamente por SKU cuando se usa `fuente=todas` o se filtra por almacen.
- **Catalogo maestro.** Cargado desde `g360-master-data` (JSON) para enriquecimiento. Auto-descarga desde GitHub en Render free. El enriquecimiento se realiza al cachear, no por request.
- **Horario laboral L–S 7:00–22:59 (Lima, -05:00).** Fuera de ese rango y domingos no se descarga, se sirve cache vencido.
- **Stale cache.** Si appweb falla, se sirve cache vencido sin reintentar hasta el proximo TTL.
- **Retry.** Reintenta 1 vez ante timeout de red.
- **Thread-safe.** Lock de descarga para evitar duplicados en concurrencia.

## Endpoints

| Metodo | Ruta | Descripcion |
|--------|------|-------------|
| `GET` | `/api/v1/health` | Estado del servicio y cache |
| `GET` | `/api/v1/stock` | Listar stock completo con filtros (siempre enriquecido) |
| `GET` | `/api/v1/stock/{sku}` | Detalle de un SKU con desglose por almacen |
| `GET` | `/api/v1/almacenes` | Lista de almacenes disponibles (filtro por tipo) |
| `GET` | `/api/v1/lineas` | Lista de lineas de producto |
| `GET` | `/api/v1/categorias` | Lista de categorias de negocio con sus lineas |
| `GET` | `/api/v1/resumen` | Resumen y KPIs del stock |
| `POST` | `/api/v1/upload/stock` | Subir archivo XLS manualmente |
| `POST` | `/api/v1/upload/catalog` | Subir catalogo maestro JSON |
| `GET` | `/api/v1/catalog/health` | Estado del catalogo cargado |
| `GET` | `/api/v1/catalog` | Lista del catalogo maestro completo (solo campos de catalogo, sin stock) |

### Parametros de GET /api/v1/stock

| Parametro | Tipo | Ejemplo | Descripcion |
|-----------|------|---------|-------------|
| `almacen` | string | `VES`, `40`, `118` | Filtrar por codigo de almacen (auto-detecta `fuente=todas` si es S*) |
| `search` | string | `CRACKCITO` | Buscar por SKU o descripcion (texto libre) |
| `linea` | string | `01`, `PELOTAS`, `78`, `AD` | Filtrar por linea (tolerante: ID o nombre) |
| `grupo` | string | `NACIONAL`, `FOLDER` | Filtrar por grupo de producto |
| `categoria` | string | `VINIBALL`, `VINIFAN` | Filtrar por categoria de negocio |
| `tipo` | string | `venta`, `mktd` | Filtrar por tipo de almacen |
| `um` | string | `UND`, `KGR`, `BST` | Filtrar por unidad de medida |
| `fuente` | string | `general`, `sucursales`, `todas` | Fuente de datos (default: `general`) |
| `limit` | int | `100` | Maximo de items a retornar (max 5000) |
| `offset` | int | `100` | Paginacion |

### Guia rapida de consultas

Esta seccion explica como combinar los filtros y que resultado esperar.

#### Filtro por tipo de almacen (`tipo`)

Clasifica automaticamente cada almacen en dos grupos:

| Valor | Que incluye | Ejemplo de uso |
|-------|-------------|----------------|
| `venta` | VES, 40, 92, 106, 121, 122, 129 | Stock de ventas tradicional |
| `mktd` | 118 + todas las S1..S17 | Marketing + sucursales |
| (omito) | todos | Sin filtro de tipo |

```
GET /api/v1/stock?tipo=mktd&limit=10
GET /api/v1/stock?tipo=venta&almacen=VES
GET /api/v1/almacenes?tipo=mktd
```

#### Filtro por fuente (`fuente`)

| Valor | Que consulta | Almacenes disponibles |
|-------|--------------|----------------------|
| `general` (default) | Cache principal | VES, 40, 92, 106, 121, 122, 129, 118 |
| `sucursales` | Cache de sucursales | S1, S2, S3, S5, S6, S9, S11, S13, S14, S15, S16, S17 |
| `todas` | Ambas fuentes combinadas | Todos los almacenes |

> **Auto-deteccion.** Si se filtra por `almacen` sin especificar `fuente`, el API usa `todas` automaticamente para incluir S*. Lo mismo aplica para `/stock/{sku}`: si el SKU existe en sucursales, se mergean los almacenes.

```
GET /api/v1/stock?fuente=sucursales&almacen=S5
GET /api/v1/stock?fuente=todas&almacen=118
GET /api/v1/stock?almacen=S5          # auto-detecta fuente=todas
GET /api/v1/stock/77145               # auto-detecta si existe en sucursales
```

#### Filtro por linea (`linea`) — tolerancia

Acepta el ID corto O el nombre completo. El filtro es case-insensitive y hace match parcial.

| Envias | Busca en | Match |
|--------|----------|-------|
| `01` | linea `"01 - PELOTAS"` | ✓ |
| `PELOTAS` | linea `"01 - PELOTAS"` | ✓ |
| `0101` | se normaliza a `01` | ✓ |
| `AD` | linea `"AD - ACCESORIOS"` | ✓ |
| `78` | linea `"78 - ARCHIVO"` | ✓ |

```
GET /api/v1/stock?linea=PELOTAS
GET /api/v1/stock?linea=01&tipo=venta
GET /api/v1/stock?linea=ARCHIVO&fuente=sucursales
```

#### Filtro por categoria (`categoria`)

Mapeo de categorias a lineas (las lineas que no encajan van a `OTROS`):

| Categoria | Lineas |
|-----------|--------|
| `VINIBALL` | 01, MA, 14, AD |
| `VINIFAN` | 02, 09, 11, 72, 73, 75, 76, 77, 78, 79, CE, CF |
| `INDUMENTARIA` | 57, 52 |
| `REPRESENTADAS` | 85 |
| `PUBLICIDAD` | 80, 81 |
| `INDUSTRIAL` | 20, 21, 23 (automatico) |
| `CIPTECH` | 30, 31, 33, 35 (automatico) |
| `MATERIALES` | 40, 50 (automatico) |
| `DESCARTE Y VARIOS` | 60, 65, 98 (automatico) |
| `PRODUCCION` | 70 (automatico) |
| `OTROS` | todo lo demas |

```
GET /api/v1/stock?categoria=VINIBALL&tipo=venta
GET /api/v1/stock?categoria=INDUSTRIAL&limit=100
```

#### Búsqueda libre (`search`)

Busca en SKU y descripcion simultaneamente. No distingue mayusculas.

```
GET /api/v1/stock?search=crackcito
GET /api/v1/stock?search=011019
GET /api/v1/stock?search=futbol
```

#### Combinacion de filtros

Todos los filtros son logicamente AND entre si. Puedes combinarlos libremente:

```
# SKUs de venta en VES que sean de pelota
GET /api/v1/stock?almacen=VES&linea=PELOTAS

# Sucursales con stock de publicidad
GET /api/v1/stock?fuente=sucursales&categoria=PUBLICIDAD

# Todo marketing con paginacion
GET /api/v1/stock?tipo=mktd&limit=50&offset=50

# Busqueda con desglose por almacen
GET /api/v1/stock/011019?fuente=todas
```

#### Orden de resultados

Los items se ordenan por SKU. Dentro de cada SKU, los almacenes se ordenan asi:
1. `VES` (almacen principal) siempre primero
2. Resto de almacenes en orden alfabetico

#### Ejemplo: flujo tipico de uso

```
# 1. Ver que almacenes tengo disponibles
GET /api/v1/almacenes

# 2. Ver resumen general
GET /api/v1/resumen

# 3. Listar productos de una categoria en venta
GET /api/v1/stock?categoria=VINIFAN&tipo=venta&limit=20

# 4. Buscar un SKU especifico y ver todas sus ubicaciones
GET /api/v1/stock/011019?fuente=todas

# 5. Ver solo mktd de una linea
GET /api/v1/stock?linea=ARCHIVO&tipo=mktd
```

### Formato de respuesta

**GET /api/v1/stock/011019:**

```json
{
  "sku": "011019",
  "descripcion": "N SEMIDEPORTIVA FUTBOL CRACKCITO BLANCO C/ROJO",
  "um": "UND",
  "linea": "01 - PELOTAS",
  "linea_id": "01",
  "grupo": "01 - NACIONAL",
  "tipo": "02 - SEMI-DEPORTIVA",
  "familia": "01 - FUTBOL",
  "categoria": "VINIBALL",
  "almacenes": [
    { "almacen": "VES", "tipo": "venta",  "stock": 6552, "predespacho": 1320, "disponible": 5232 },
    { "almacen": "118", "tipo": "mktd",   "stock": 4,     "predespacho": 0,    "disponible": 4 },
    { "almacen": "40",  "tipo": "venta",  "stock": 36,    "predespacho": 0,    "disponible": 36 }
  ],
  "estado_linea": "NACIONAL",
  "un_bx": 60,
  "peso_kg": 0.2,
  "precio": 9.16,
  "nombre_corto": "Semideportiva Futbol Crackcito Blanco C/Rojo",
  "ean13": "7754807110198",
  "ean14": "",
  "keywords": ["BLANCO", "C/ROJO", "CRACKCITO", "FUTBOL", "PELOTAS", "SEMIDEPORTIVA", "VINIBALL"],
  "orden": 2,
  "sin_catalogo": false
}
```

> **Nota sobre enriquecimiento.** Todos los endpoints retornan los campos extendidos (`precio`, `ean13`, `keywords`, etc.) de forma automatica. El enriquecimiento se realiza al cachear los datos (no por request), lo que garantiza consistencia y performance. Si el catalogo maestro no esta cargado, estos campos llegan con valores por defecto (`0`, `""`, `false`) y `metadata.enriquecido` sera `false`. Al subir un catalogo nuevo via `/api/v1/catalog/upload`, los items se re-enriquecen automaticamente.

## Tipos de almacen

| Tipo | Almacenes |
|------|-----------|
| `venta` | VES, 40, 92, 106, 121, 122, 129 |
| `mktd` | 118, S1, S2, S3, S5, S6, S9, S11, S13, S14, S15, S16, S17 |

El tipo se refleja en cada item del array `almacenes[].tipo`. El endpoint `/almacenes` permite filtrar por tipo con `?tipo=venta` o `?tipo=mktd`.

## Fuentes de datos

| Fuente | URL appweb | Almacenes | Cache |
|--------|-----------|-----------|-------|
| `general` | `parametroX2=""` | VES, 40, 92, 106, 121, 122, 129, 118 | `data/stock_cache.json` |
| `sucursales` | `parametroX2="1"` | S1, S2, S3, S5, S6, S9, S11, S13, S14, S15, S16, S17 | `data/stock_cache_sucursales.json` |
| `todas` | ambas | ambos, mergeados por SKU sin duplicados | ambas |

Las dos fuentes se descargan y cachean de forma independiente. Al consultar con `fuente=todas`, los items se mergean por SKU combinando sus almacenes, garantizando cero duplicados.

## Catalogo maestro

El catalogo se carga desde `g360-master-data` (JSON generado externamente):
- **`/api/v1/upload/catalog`** — subir archivo JSON manualmente
- **Auto-carga** — al iniciar, si no hay catalogo en disco, se descarga desde GitHub raw
- **TTL** — 6 horas (21600s)
- **Campos usados**: `sku`, `linea`, `grupo`, `tipo`, `familia`, `categoria`, `ean13`, `ean14`, `un_bx`, `peso_kg`, `precio`, `keywords`, `nombre_corto`

## Cache

Archivos de cache en `data/`:
- `stock_cache.json` — fuente general
- `stock_cache_sucursales.json` — fuente sucursales
- `catalog_cache.json` — catalogo maestro

Cada uno con backup rotativo (`.bak`) que se activa si el principal se corrompe. Los items se enriquecen con el catalogo al momento de cachear, no en cada request.

### Reglas de refresco

1. **Sin cache** → descarga forzada (sin importar dia/hora).
   Nunca responde vacio: es preferible un error que data incorrecta o ninguna.
2. **Cache vigente** (< TTL) → sirve del cache.
3. **Cache vencido + horario valido** (L-S 7:00–22:59 Lima) → descarga fresh.
4. **Cache vencido + horario invalido** (noche o domingo) → sirve cache vencido.
   El campo `metadata.cache_expirado=true` avisa al consumidor.
5. **Descarga falla + hay cache** → sirve cache vencido, reintenta en ~15 min.

## Lineas de producto

**34 lineas** distribuidas en 10 categorias de negocio. Top lineas por volumen:

| Linea | SKUs | Categoria |
|-------|------|-----------|
| ARCHIVO | 318 | VINIFAN |
| PELOTAS | 298 | VINIBALL |
| REPRESENTACIONES INDUSTRIALES | 201 | INDUSTRIAL |
| REPRESENTADAS | 195 | REPRESENTADAS |
| PRODUCTOS INDUSTRIALES | 181 | INDUSTRIAL |
| INDUMENTARIA Y EPP | 162 | INDUMENTARIA |
| ESCRITURA | 160 | VINIFAN |
| PUBLICIDAD | 112 | PUBLICIDAD |
| ACCESORIOS | 96 | VINIFAN |
| PINTURA | 103 | VINIFAN |

Total: **2,184 SKUs** en fuente general, **798 SKUs** en sucursales, **2,982 SKUs** combinados.

## Categorias de negocio

| Categoria | Lineas principales | SKUs |
|-----------|-------------------|------|
| VINIFAN | 02, 09, 11, 72-79, CE, CF | ~1,000 |
| VINIBALL | 01, MA, 14, AD | ~350 |
| INDUSTRIAL | 20, 21, 23 | ~420 |
| REPRESENTADAS | 85 | 195 |
| INDUMENTARIA | 52, 57 | 163 |
| PUBLICIDAD | 80, 81 | 119 |
| MATERIALES | 40, 50 | 60 |
| CIPTECH | 30, 31, 33, 35 | 20 |
| DESCARTE Y VARIOS | 60, 65, 98 | 47 |
| PRODUCCION | 70 | 9 |
| OTROS | - | 15 |

## Estructura del proyecto

```
g360-stock-api/
├── app/
│   ├── core/
│   │   ├── constants.py      # Columnas XLS, categorias, lineas, almacenes, prefijos
│   │   ├── parsers.py         # Parser XLS con headers de categoria (LINEA/GRUPO/TIPO/FAMILIA)
│   │   └── xls_fallback.py    # Lector XLS multiformato (openpyxl, xlrd, csv, html, xml)
│   ├── models/
│   │   └── schemas.py         # Pydantic models (ItemStockEnriched, StockEnrichedResponse, etc.)
│   ├── routers/
│   │   ├── health.py          # GET /api/v1/health
│   │   ├── stock.py           # GET /api/v1/stock, /{sku}, /lineas, /almacenes, /categorias
│   │   ├── upload.py          # POST /api/v1/upload (XLS manual)
│   │   ├── resumen.py         # GET /api/v1/resumen
│   │   └── catalog.py         # POST /api/v1/catalog/upload, GET /api/v1/catalog, GET /api/v1/catalog/health
│   ├── services/
│   │   ├── s1_service.py      # Logica: descarga, parseo, cache dual, enriquecimiento, filtros
│   │   └── catalog_service.py # Gestion del catalogo maestro en memoria con TTL
│   ├── config.py              # Settings via pydantic-settings
│   └── main.py                # FastAPI app con CORS, auth y routers
├── tests/
│   ├── samples/               # REPT_STOCK_SAMPLE.xls (reemplazado por reporte completo)
│   ├── test_api.py            # Tests de integracion
│   ├── test_catalog.py        # Tests de catalogo (upload, health, enrich)
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
| `S1_API_KEY` | `""` | API Key para proteger endpoints. Vacío = sin auth |
| `S1_SOURCE1_URL` | URL appweb | Fuente general (parametroX2="") |
| `S1_SOURCE2_URL` | URL appweb | Fuente sucursales (parametroX2="1") |
| `S1_CACHE_TTL_SEGUNDOS` | `900` | TTL del cache de stock (15 min) |
| `S1_CACHE_RUTA` | `data/stock_cache.json` | Cache de fuente general |
| `S1_CACHE_RUTA2` | `data/stock_cache_sucursales.json` | Cache de fuente sucursales |
| `S1_CATALOGO_RUTA` | `data/catalog_cache.json` | Cache del catalogo maestro |
| `S1_CATALOGO_TTL_SEGUNDOS` | `21600` | TTL del catalogo (6 horas) |
| `S1_CATALOGO_RAW_URL` | URL GitHub | Fuente remota del catalogo para auto-carga |
| `S1_PUERTO` | `8000` | Puerto del servidor |

### Autenticacion (opcional)

Si se configura `S1_API_KEY`, todos los endpoints requieren el header:

```
X-API-Key: tu-clave-secreta
```

Sin el header o con clave incorrecta → `403 Forbidden`. Si `S1_API_KEY` esta vacio (default), la API es abierta.

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

Tests que cubren:
- Parseo de XLS (formato con headers de categoria en columnas separadas)
- Filtros por almacen, busqueda, linea, grupo, categoria, tipo, UM
- Calculo de disponible (stock - predespacho, nunca negativo)
- Enriquecimiento con catalogo maestro (linea_id, ean, precio, keywords, etc.)
- Cache, backup .bak, upload de XLS y catalogo
- Health, almacenes (con filtro por tipo), lineas, categorias
- 404, subida sin archivo, catalog health

## Deploy en Render

El repositorio incluye `stock_cipsa.yaml` (Blueprints). Pasos:

1. Crear repositorio en GitHub y subir el proyecto
2. Render Dashboard → New → Blueprint → seleccionar repositorio
3. Render detecta `stock_cipsa.yaml` y configura automaticamente
4. Opcional: ajustar variables de entorno en Render Dashboard

## Licencia

Proyecto interno del ecosistema **G360 - CIPSA**.
