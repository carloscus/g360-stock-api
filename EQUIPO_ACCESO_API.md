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
    {"almacen": "VES", "stock": 63400, "disponible": 63400},
    {"almacen": "40", "stock": 7000, "disponible": 7000}
  ],
  "precio": 10.25,
  "ean13": "7754807020015",
  "un_bx": 25,
  "sin_catalogo": false
}
```

---

## Almacenes disponibles

| Tipo | Almacenes |
|------|-----------|
| **Venta** | VES, 40, 92, 106, 121, 122, 129 |
| **Marketing** | 118, S1, S2, S3, S5, S6, S9, S11, S13, S14, S15, S16, S17 |

---

## Nota para desarrolladores

- La API tiene **rate limiting**: máximo 60 requests/minuto por IP
- Los datos se cachean cada 15 minutos (TTL configurable)
- Si la API responde `cache_expirado: true`, los datos pueden estar desactualizados
- El horario de actualización automática es Lun-Sáb 7:00-22:59 (Lima)

---

**API version:** 1.3.0  
**Repositorio:** https://github.com/carloscus/g360-stock-api  
**Swagger docs:** https://g360-stock-api.onrender.com/docs
