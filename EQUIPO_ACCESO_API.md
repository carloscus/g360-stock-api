# G360 Stock API — Acceso para el equipo

## URL base
```
https://g360-stock-api.onrender.com/api/v1/stock
```

## Autenticación
Todas las peticiones requieren el header:
```
X-API-Key: [TU_API_KEY]
```
> **Excepción:** `GET /api/v1/health` es **público** (sin key) para que el healthcheck de Render funcione.

## Documentación interactiva
```
https://g360-stock-api.onrender.com/docs
```

---

## Endpoints principales

### 1. Listar stock (filtro por almacen)
```
GET /api/v1/stock?almacen=S5&limit=10
```
**Nota:** Si el almacen es S*, el API usa `fuente=todas` automáticamente y mergea VES + sucursales.

### 2. Buscar SKU específico
```
GET /api/v1/stock/02217
```
Devuelve todos los almacenes donde existe el SKU (VES, S5, etc.)

### 3. Resumen y KPIs
```
GET /api/v1/resumen
```
Total de SKUs, almacenes con stock, predespachados, etc.

### 4. Estado del servicio
```
GET /api/v1/health
```
Hora de última descarga, si el cache es válido, cantidad de SKUs.

### 5. Lista de almacenes
```
GET /api/v1/almacenes
GET /api/v1/almacenes?tipo=mktd
GET /api/v1/almacenes?tipo=venta
```

### 6. Universo consolidado (una fila por SKU)
```
GET /api/v1/stock/skus?fuente=todas
```
No repite el SKU por almacén: devuelve `stock`, `predespacho` y `disponible`
totales por SKU, más la ficha mínima (línea, grupo, tipo, familia, UM,
categoría). Es el endpoint que usa `g360-master-data` para generar el catálogo.
Con `solo_con_movimiento=false` incluye también los SKU sin stock.

### Flags de negocio en la respuesta

Cada item trae estos flags (los publica el catálogo maestro):

| Flag | Para qué sirve |
|------|----------------|
| `categoria_venta` | `VINIBALL`, `VINIFAN`, `REPRESENTADAS` o `REVISION_VENTA` (no cotizar hasta revisar) |
| `cotizable` / `por_activar` | Tiene precio / está publicado pero sin precio |
| `en_guia` | Está curado en la guía de venta (SKU_BX) |
| `compromiso` | Tenía predespacho al generar el catálogo |
| `vigente` | El ERP no lo marca descontinuado |
| `origen` | `erp` (ficha del maestro) o `s1` (solo existe en el reporte) |
| `derivado_de` | SKU base si es un derivado sin embalaje (línea 98) |
| `revision` | Badge: `sin_catalogo`, `por_activar`, `revision_venta`, `descontinuado`, `compromiso` o `""` |

> Si un SKU aparece con `sin_catalogo: true`, tiene stock pero no está en el
> catálogo maestro: avisar para publicarlo (no tiene precio, peso ni caja).

---

## Ejemplos de uso

### Desde curl (terminal)
```bash
curl -H "X-API-Key: cipsa2026" \
  "https://g360-stock-api.onrender.com/api/v1/stock?almacen=VES&limit=5"

curl -H "X-API-Key: cipsa2026" \
  "https://g360-stock-api.onrender.com/api/v1/stock/02217"
```

### Desde JavaScript/Frontend
```javascript
const API_KEY = '[TU_API_KEY]';
const BASE_URL = 'https://g360-stock-api.onrender.com/api/v1';

// Listar stock de VES
const response = await fetch(`${BASE_URL}/stock?almacen=VES&limit=20`, {
  headers: { 'X-API-Key': API_KEY }
});
const data = await response.json();

// Buscar un SKU
const sku = await fetch(`${BASE_URL}/stock/02217`, {
  headers: { 'X-API-Key': API_KEY }
});
```

### Desde Python
```python
import requests

API_KEY = '[TU_API_KEY]'
BASE_URL = 'https://g360-stock-api.onrender.com/api/v1'

headers = {'X-API-Key': API_KEY}

# Stock de sucursales
r = requests.get(f'{BASE_URL}/stock?almacen=S5', headers=headers)
print(r.json())

# Nota: cada almacen incluye 'nombre' con el nombre descriptivo
# Ejemplo: {"almacen": "S11", "nombre": "ALMACEN SUCURSAL CAJAMARCA", ...}
```

---

## Filtros disponibles

| Filtro | Ejemplo | Descripción |
|--------|---------|-------------|
| `almacen` | `?almacen=S5` | Filtrar por almacén (auto-detecta sucursales) |
| `search` | `?search=crackcito` | Buscar por SKU o descripción |
| `linea` | `?linea=PELOTAS` | Por ID (01) o nombre (PELOTAS) |
| `categoria` | `?categoria=VINIFAN` | VINIBALL, VINIFAN, INDUSTRIAL, etc. |
| `tipo` | `?tipo=mktd` | venta / mktd |
| `fuente` | `?fuente=todas` | general / sucursales / todas |
| `limit` | `?limit=50` | Máximo de items (max 5000) |

---

## Respuesta típica (SKU 02217)

```json
{
  "sku": "02217",
  "descripcion": "FORRO N VINIFAN OFICIO CRISTAL 27",
  "linea": "02 - FORROS",
  "categoria": "VINIFAN",
  "almacenes": [
    {"almacen": "VES", "nombre": "CENTRO LOGISTICO VES", "stock": 63400, "disponible": 63400},
    {"almacen": "40", "nombre": "ALMACEN PROD. TERMINADOS", "stock": 7000, "disponible": 7000}
  ],
  "precio": 10.25,
  "ean13": "7754807020015",
  "un_bx": 25,
  "sin_catalogo": false,
  "sin_stock": false
}
```

> **Nota:** Cada almacén incluye el campo `nombre` con el nombre descriptivo
> (ej: "ALMACEN SUCURSAL CAJAMARCA"). Si no hay nombre disponible, se retorna
> el mismo ID del almacén.

### ¿Qué significa el flag `sin_stock`?

Consulta un SKU que todavía no aparece en el reporte de stock pero existe en el catálogo maestro:
`GET /api/v1/stock/76250` → **200 OK** con la ficha y `sin_stock: true`:

```json
{
  "sku": "76250",
  "linea": "ESCRITURA",
  "un_bx": 28,
  "precio": 17.77,
  "sin_catalogo": false,
  "sin_stock": true,
  "almacenes": []
}
```

Leer los tres estados:

| Estado | Respuesta | Significado |
|--------|-----------|-------------|
| `sin_stock: true` | 200 OK | Producto vigente en catálogo, aún sin stock en el reporte (ingreso futuro) |
| `sin_catalogo: true` | 200 OK | Tiene stock pero la ficha está incompleta (falta en el catálogo) |
| **404** | error | El SKU no existe ni en el reporte ni en el catálogo |

---

## Almacenes disponibles

| Tipo | Almacenes |
|------|-----------|
| **Venta** | VES, 40, 92, 106, 121, 122, 129 |
| **Marketing** | 118, S1, S2, S3, S5, S6, S9, S11, S13, S14, S15, S16, S17 |

---

## Nota para desarrolladores

- La API tiene **rate limiting**: máximo 60 requests/minuto por IP
- Los datos se cachean cada 10 minutos (TTL configurable)
- Si la API responde `cache_expirado: true`, los datos pueden estar desactualizados
- El horario de actualización automática es Lun-Sáb 7:00-22:59 (Lima)

---

## Para nuevas apps consumidoras

### 1. Obtener API Key

Consulta con el equipo de sistemas para recibir tu clave de acceso. La key se configura en:
- Variables de entorno: `G360_S1_API_KEY`
- Config local: `.env` o settings del proyecto

### 2. Patrones recomendados

```python
# patron 1: Consulta por SKU (ficha completa)
GET /api/v1/stock/{sku}

# patron 2: Filtro por almacén específico
GET /api/v1/stock?almacen=S5&limit=100

# patron 3: Universo consolidado (una fila por SKU)
GET /api/v1/stock/skus?fuente=todas&solo_con_movimiento=true

# patron 4: Verificar estado del servicio
GET /api/v1/health  # sin API key requerida
```

### 3. Manejo de errores

| Código | Significado | Acción |
|--------|-------------|--------|
| 200 | OK | Datos válidos |
| 403 | Key inválida | Verificar X-API-Key |
| 404 | SKU no existe | Verificar en catálogo maestro |
| 429 | Rate limit | Esperar y reintentar |
| 504 | Timeout | Verificar health, reintentar |

### 4. Cache local sugerido

Para reducir llamadas al API, recomenda cachear respuestas:
- SKU individual: TTL 10 min
- Listados: TTL 5 min
- Health: TTL 1 min

### 5. Ejemplo completo

```python
import requests
import time
from functools import lru_cache

API_KEY = "tu-api-key"
BASE_URL = "https://g360-stock-api.onrender.com/api/v1"

@lru_cache(maxsize=1000)
def get_stock(sku: str, cache_time: int = 600):
    """Obtiene stock de un SKU con cache local."""
    headers = {"X-API-Key": API_KEY}
    r = requests.get(f"{BASE_URL}/stock/{sku}", headers=headers, timeout=30)
    if r.status_code == 200:
        return r.json()
    return None

# Uso
sku_data = get_stock("011019")
if sku_data:
    print(f"SKU: {sku_data['sku']}")
    print(f"Linea: {sku_data['linea']}")
    for alm in sku_data.get('almacenes', []):
        print(f"  {alm['nombre']}: {alm['disponible']} disp")
```

---

**API version:** 1.7.0  
**Repositorio:** https://github.com/carloscus/g360-stock-api  
**Swagger docs:** https://g360-stock-api.onrender.com/docs
