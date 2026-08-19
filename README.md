# g360-stock-api

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="logotypes/logo-g360-light.svg">
  <img alt="G360 Stock API" height="64" src="logotypes/logo-g360-dark.svg">
</picture>

> API REST para el reporte de stock S1 desde **appweb.cipsa.com.pe**. Descarga, parsea y sirve stock de VES + sucursales enriquecido con catálogo maestro.

[![Version](https://img.shields.io/badge/version-1.3.0-blue)](https://github.com)
[![Skill](https://img.shields.io/badge/skill-cipsa-green)](https://github.com/carloscus/g360-cli)
[![Python](https://img.shields.io/badge/python-3.10+-blue)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-green)](https://fastapi.tiangolo.com/)

## ¿Cómo está organizado el proyecto?

```mermaid
flowchart TD
    ERP["appweb.cipsa.com.pe<br/>XLS General + Sucursales"]
    MASTER["g360-master-data<br/>catalogo_productos.json"]

    subgraph API["g360-stock-api"]
        CACHE1["stock_cache.json<br/>(general: VES, 40, 92...)"]
        CACHE2["stock_cache_sucursales.json<br/>(S1, S2, S3...)"]
        CAT_CACHE["catalog_cache.json<br/>(2393 SKUs)"]
        ENRICH["enriquecimiento<br/>(al cachear, no por request)"]
        MERGE["_merge_items_por_sku<br/>(sin duplicados)"]
    ]

    ERP -->|parametroX2=""| CACHE1
    ERP -->|parametroX2="1"| CACHE2
    MASTER -->|auto-download| CAT_CACHE
    CACHE1 & CACHE2 --> ENRICH
    CAT_CACHE --> ENRICH
    ENRICH --> MERGE

    subgraph ENDPOINTS["Endpoints REST"]
        STOCK["GET /api/v1/stock"]
        SKU["GET /api/v1/stock/{sku}"]
        ALM["GET /api/v1/almacenes"]
        RESUMEN["GET /api/v1/resumen"]
        CAT["GET /api/v1/catalog"]
    end

    MERGE --> STOCK
    MERGE --> SKU
    CACHE1 & CACHE2 --> ALM
    CACHE1 --> RESUMEN
    CAT_CACHE --> CAT
```

## Tabla de Contenidos

- [Descripción](#descripción)
- [Arquitectura](#arquitectura)
- [Endpoints](#endpoints)
- [Guía rápida](#guía-rápida)
- [Protecciones](#protecciones)
- [Tipos de almacén](#tipos-de-almacén)
- [Fuentes de datos](#fuentes-de-datos)
- [Catálogo maestro](#catálogo-maestro)
- [Cache](#cache)
- [Configuración](#configuración)
- [Desarrollo](#desarrollo)
- [Deploy en Render](#deploy-en-render)
- [Ecosistema G360](#ecosistema-g360)

---

## Descripción

API REST que consume los reportes de stock desde appweb.cipsa.com.pe (ERP CIPSA), los descarga, parsea y sirve como JSON estructurado. Combina dos fuentes (general + sucursales) y las enriquece con el catálogo maestro de productos.

**Tipo**: API REST / Backend  
**Runtime**: Python 3.10+ / FastAPI / Uvicorn  
**Uso**: Frontend estático (GitHub Pages) + app interno CIPSA

---

## Arquitectura

```mermaid
sequenceDiagram
    participant FE as Frontend CIPSA
    participant API as g360-stock-api
    participant APPWEB as appweb.cipsa.com.pe
    participant GH as GitHub (master-data)

    FE->>API: GET /stock?almacen=S5
    API->>API: _refrescar_si_es_necesario()
    alt Cache vigente (<15 min)
        API-->>FE: Datos enriquecidos (cache)
    else Cache vencido + horario valido
        API->>APPWEB: Descargar XLS (1x)
        APPWEB-->>API: XLS response
        API->>API: Parsear + transformar
        API->>API: Enriquecer con catálogo
        API->>API: Guardar cache + .bak
        API-->>FE: Datos frescos
    else Cache vencido + fuera horario
        API-->>FE: Cache viejo (cache_expirado=true)
    end

    Note over API,GH: Catálogo auto-refresh cada 6h
    API->>GH: GET catalogo_productos.json
    GH-->>API: JSON catálogo
    API->>API: Re-enriquecer items
```

---

## Endpoints

| Método | Ruta | Descripción |
|--------|------|-------------|
| `GET` | `/api/v1/health` | Estado del servicio y cache |
| `GET` | `/api/v1/stock` | Listar stock completo con filtros (enriquecido) |
| `GET` | `/api/v1/stock/{sku}` | Detalle de un SKU con desglose por almacén |
| `GET` | `/api/v1/almacenes` | Lista de almacenes disponibles |
| `GET` | `/api/v1/lineas` | Lista de líneas de producto |
| `GET` | `/api/v1/categorias` | Categorías de negocio con líneas |
| `GET` | `/api/v1/resumen` | Resumen y KPIs del stock |
| `POST` | `/api/v1/upload/stock` | Subir archivo XLS manualmente |
| `POST` | `/api/v1/upload/catalog` | Subir catálogo maestro JSON |
| `GET` | `/api/v1/catalog` | Lista del catálogo maestro (sin stock) |
| `GET` | `/api/v1/catalog/health` | Estado del catálogo cargado |

### Parámetros de GET /api/v1/stock

| Parámetro | Tipo | Ejemplo | Descripción |
|-----------|------|---------|-------------|
| `almacen` | string | `VES`, `40`, `S5` | Filtrar por código (auto-detecta fuente=todas si es S*) |
| `search` | string | `CRACKCITO` | Buscar por SKU o descripción |
| `linea` | string | `01`, `PELOTAS` | Filtrar por línea (tolerante: ID o nombre) |
| `grupo` | string | `NACIONAL` | Filtrar por grupo |
| `categoria` | string | `VINIBALL` | Filtrar por categoría de negocio |
| `tipo` | string | `venta`, `mktd` | Filtrar por tipo de almacén |
| `um` | string | `UND`, `KGR` | Filtrar por unidad de medida |
| `fuente` | string | `general`, `sucursales`, `todas` | Fuente de datos (default: general) |
| `limit` | int | `100` | Máximo de items (max 5000) |
| `offset` | int | `100` | Paginación |

---

## Guía rápida

### Auto-detección inteligente

```
GET /api/v1/stock?almacen=S5     → fuente=todas automáticamente
GET /api/v1/stock/77145          → mergea almacenes si existe en sucursales
GET /api/v1/stock?linea=ARCHIVO  → busca "02 - ARCHIVO" o "ARCHIVO"
```

### Ejemplos típicos

```bash
# Ver todos los SKUs en VES
GET /api/v1/stock?almacen=VES&limit=20

# Sucursales con stock de pintura
GET /api/v1/stock?fuente=sucursales&categoria=VINIFAN&linea=PINTURA

# Marketing + sucursales combinados
GET /api/v1/stock?tipo=mktd

# Detalle completo de SKU
GET /api/v1/stock/011019?fuente=todas

# Resumen ejecutivo
GET /api/v1/resumen

# Estado del servicio
GET /api/v1/health
```

---

## Protecciones

| Capa | Qué hace | Qué previene |
|------|----------|--------------|
| **Rate limiting** | 60 req/min por IP | Saturación, abuso |
| **Request timeout** | 30s max, devuelve 504 | Requests colgados |
| **Circuit breaker** | 3 fallos → pausa 5 min | Caída en cascada |
| **Cache stale** | Sirve datos viejos si appweb cae | Respuestas vacías |
| **XLS size limit** | 5MB max por descarga | Memoria agotada |
| **Thread-safe lock** | 1 descarga por fuente a la vez | Duplicados |
| **CORS** | Orígenes configurables | Acceso no autorizado |
| **API Key** | Header X-API-Key requerido | Acceso sin auth |
| **GZip** | Compresión automática >500 bytes | Ancho de banda |
| **Request logging** | method, path, status, elapsed, IP | Trazabilidad |

### Circuit breaker en detalle

```
Request → Cache vencido + horario válido
  → Intenta descargar de appweb
  → Falla (timeout, 500, red)
  → _cb_fallos += 1

3 fallos consecutivos:
  → Circuito ABIERTO por 5 minutos
  → No intenta descargar, sirve cache vencido

Después de 5 min:
  → Circuito se CIERRA
  → Siguiente request intenta descargar de nuevo
```

---

## Tipos de almacén

| Tipo | Almacenes |
|------|-----------|
| `venta` | VES, 40, 92, 106, 121, 122, 129 |
| `mktd` | 118, S1, S2, S3, S5, S6, S9, S11, S13, S14, S15, S16, S17 |

---

## Fuentes de datos

| Fuente | URL appweb | Almacenes | Cache |
|--------|-----------|-----------|-------|
| `general` | `parametroX2=""` | VES, 40, 92, 106, 121, 122, 129, 118 | `data/stock_cache.json` |
| `sucursales` | `parametroX2="1"` | S1, S2, S3, S5, S6, S9, S11, S13, S14, S15, S16, S17 | `data/stock_cache_sucursales.json` |
| `todas` | ambas | ambos, mergeados por SKU sin duplicados | ambas |

---

## Catálogo maestro

Cargado desde `g360-master-data` (JSON en GitHub):
- **`/api/v1/upload/catalog`** — subir archivo JSON manualmente
- **Auto-carga** — al iniciar, si no hay catálogo en disco, descarga desde GitHub
- **Auto-refresh** — cuando TTL expira (6h), refresca automáticamente desde GitHub
- **TTL** — 6 horas (21600s)

Campos usados: `sku`, `linea`, `grupo`, `tipo`, `familia`, `categoria`, `ean13`, `ean14`, `un_bx`, `peso_kg`, `precio`, `keywords`, `nombre_corto`

---

## Cache

Archivos en `data/`:
- `stock_cache.json` — fuente general
- `stock_cache_sucursales.json` — fuente sucursales
- `catalog_cache.json` — catálogo maestro

Backup rotativo (`.bak`) si el principal se corrompe. Los items se enriquecen **al cachear**, no por request.

### Reglas de refresco

1. **Sin cache** → descarga forzada (sin importar día/hora)
2. **Cache vigente** (< TTL) → sirve directo
3. **Cache vencido + horario válido** (L-S 7:00–22:59 Lima) → descarga fresh
4. **Cache vencido + fuera de horario** → sirve cache vencido (`cache_expirado=true`)
5. **Descarga falla + hay cache** → sirve cache vencido, reintenta en ~15 min

---

## Configuración

Variables de entorno (prefix `S1_`):

### Fuentes de datos

| Variable | Default | Descripción |
|----------|---------|-------------|
| `S1_SOURCE1_URL` | URL appweb | Fuente general |
| `S1_SOURCE2_URL` | URL appweb | Fuente sucursales |
| `S1_CACHE_TTL_SEGUNDOS` | `900` | TTL del cache de stock (15 min) |
| `S1_CACHE_RUTA` | `data/stock_cache.json` | Cache general |
| `S1_CACHE_RUTA2` | `data/stock_cache_sucursales.json` | Cache sucursales |
| `S1_CATALOGO_RUTA` | `data/catalog_cache.json` | Cache catálogo |
| `S1_CATALOGO_TTL_SEGUNDOS` | `21600` | TTL del catálogo (6 horas) |
| `S1_CATALOGO_RAW_URL` | URL GitHub | Fuente remota del catálogo |
| `S1_PUERTO` | `8000` | Puerto del servidor |

### Seguridad y protecciones

| Variable | Default | Descripción |
|----------|---------|-------------|
| `S1_API_KEY` | `""` | API Key administrativa. **Setear en Render** |
| `S1_READ_API_KEY` | `""` | API Key de lectura para frontend |
| `S1_RATE_LIMIT` | `60/minute` | Rate limiting por IP |
| `S1_REQUEST_TIMEOUT` | `30` | Timeout en segundos |
| `S1_CORS_ORIGINS` | `*` | Orígenes CORS permitidos |
| `S1_CIRCUIT_BREAKER_MAX_FALLOS` | `3` | Fallos antes de abrir circuito |
| `S1_CIRCUIT_BREAKER_RESET_SEG` | `300` | Segundos para resetear circuito |
| `S1_XLS_MAX_BYTES` | `5242880` | Máximo tamaño de XLS (5 MB) |

---

## Desarrollo

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Documentación interactiva en `http://localhost:8000/docs`.

### Tests

```bash
pytest tests/ -v
```

---

## Deploy en Render

El repositorio incluye `stock_cipsa.yaml` (Blueprints). Pasos:

1. Crear repositorio en GitHub y subir el proyecto
2. Render Dashboard → New → Blueprint → seleccionar repositorio
3. Render detecta `stock_cipsa.yaml` y configura automáticamente
4. Configurar variables de entorno en Render Dashboard:
   - `S1_API_KEY` → clave administrativa
   - `S1_READ_API_KEY` → clave de lectura (frontend)
   - `S1_CORS_ORIGINS` → dominios permitidos

---

## Ecosistema G360

Este proyecto forma parte del ecosistema **G360** para apoyo CRM y gestión de datos en CIPSA.

### Herramientas relacionadas

- **[g360-cli](https://github.com/carloscus/g360-cli)** — CLI para inicializar proyectos G360
- **[g360-master-data](https://github.com/carloscus/g360-master-data)** — Catálogo maestro de productos
- **[g360-stock-reporter-lit](https://github.com/carloscus/g360-stock-reporter-lit)** — Frontend PWA
- **[g360-erp-stock-monitor](https://github.com/carloscus/g360-erp-stock-monitor)** — Monitor de stock en tiempo real

---

## Licencia

Proyecto interno del ecosistema **G360 - CIPSA**.

---

**Marca**: G360 · Microherramientas para apoyo CRM y datos en CIPSA  
**Isotipo**: 3 puntos verticales paralelos (gris-verde-gris) + chevron `>`  
**Signature**: G360 by ccusi  
**Powered by**: [g360-signature](https://github.com/carloscus/g360-signature)

> Identidad generada desde `src/assets/brand/brand.json` (Brand System v2.0.0).  
> El logo arriba usa `<picture>` con `prefers-color-scheme` para light/dark.
