---
deck: G360 Stock API: manual de acceso para el equipo
audience: Equipo G360 que consume stock: saben leer endpoints y headers, quieren listo el URL, la clave, los filtros y un ejemplo por lenguaje sin pedir ayuda.
register: read
structure: Creamos una tapa en ink, giros de sección en ink y cierre en ink; la evidencia (endpoints, tablas, código) en paper.
motif: La línea de terminal repite en cada slide operativo: el comando real de la consulta que se está explicando.
---

## Slide 1
layout: title
Canvas: ink
Title: G360 Stock API
Subtitle: Manual de acceso para el equipo · v1.4.0
Brief: Tapa clara (ink) con el nombre del servicio; el motivo asoma como una línea de terminal dibujada a la derecha, con la URL base y la promesa de que todo lo que sigue es una llamada.
Notes: La tapa presenta el manual y su versión. El equipo sale de esta nota sabiendo que cada consulta es una URL + un header, y que todo lo demás son ejemplos de esa llamada.

## Slide 2
layout: section
Canvas: ink
Title: 01 · Conexión
Brief: Giro claro que abre la primera parte del manual: dónde vive la API y cómo se autentica.
Notes: Primera sección: una URL base, un header X-API-Key y una sola excepción. El resto son detalles de ese contrato.

## Slide 3
layout: composed
Title: Una URL y un header
Brief: Las cuatro tarjetas fijan los datos que hay que recordar; el header es el héroe porque es la única línea que se repite en cada llamada.
Block: card-grid
Base URL | https://g360-stock-api.onrender.com / /api/v1/stock
! Header | X-API-Key en / todas las peticiones
Excepción | /health: público / solo para Render
Docs | /docs: Swagger / interactivo
Notes: La URL base es la raíz de cada llamada. Toda petición lleva el header X-API-Key; la única excepción es /health, que queda público de propósito para que el healthcheck de Render funcione. Swagger interactivo en /docs para probar sin escribir código.

## Slide 4
layout: section
Canvas: ink
Title: 02 · Endpoints
Brief: Giro claro que abre el cuerpo del manual: las cinco consultas operativas.
Notes: Segunda sección: listar stock, un SKU, resumen, health y almacenes. Cada slide siguiente muestra el comando exacto de una consulta.

## Slide 5
layout: composed
Title: Listar stock por almacén
Brief: El comando ocupa la mitad superior; los tres chips de abajo aclaran los parámetros que importan. La S* merece su nota porque cambia el comportamiento.
Block: freeform
text body ink at cols 1-12 rows 2-3 | GET /api/v1/stock?almacen=S5&limit=10
Block: card-grid
almacen=S5 | filtra la bodega
! S* | fuente=todas: mergea / VES + sucursales
limit=10 | máximo de items
Notes: Si el almacen es una S*, la API usa fuente=todas de forma automática y devuelve VES más sucursales combinadas. limit recorta el tamaño de la respuesta.

## Slide 6
layout: composed
Title: Un SKU, todas sus bodegas
Brief: El comando arriba; la ficha real de 02217 abajo como evidencia de que la respuesta trae todos los almacenes donde existe el producto.
Block: freeform
text body ink at cols 1-12 rows 2-3 | GET /api/v1/stock/02217
Block: stat-row
63.400 | unidades en VES
7.000 | unidades en 40
Notes: La consulta por SKU devuelve todos los almacenes donde existe: la ficha de 02217 muestra 63.400 unidades en VES y 7.000 en el almacén 40, con precio, EAN y unidades por caja.

## Slide 7
layout: composed
Title: Tres consultas de estado
Brief: Un trío de tarjetas: cada consulta de mantenimiento con lo que devuelve. Ninguna compite por el ojo; el endpoint es el lead.
Block: card-grid
! /resumen | KPIs: total de SKUs, / almacenes con stock, predespachados
/health | hora de última descarga, / cache válido, nº de SKUs
/almacenes | listado por tipo: / venta o mktd
Notes: Tres endpoints de estado: /resumen devuelve métricas agregadas; /health informa la última descarga y si el cache es válido; /almacenes lista las bodegas, filtrable por tipo=venta o tipo=mktd.

## Slide 8
layout: section
Canvas: ink
Title: 03 · En el código
Brief: Giro claro que abre la tercera parte: la misma llamada en tres lenguajes.
Notes: Tercera sección: el mismo header y la misma URL en curl, JavaScript y Python.

## Slide 9
layout: composed
Title: curl
Brief: Dos comandos de terminal, el motivo en su forma más pura: listar y buscar un SKU, listos para copiar y pegar.
Block: freeform
text body ink at cols 1-12 rows 2-3 | GET /api/v1/stock?almacen=VES&limit=5
text body ink at cols 1-12 rows 4-5 | GET /api/v1/stock/02217
Notes: Para probar desde la terminal: listar stock de VES y consultar un SKU puntual. La clave va en el header X-API-Key, igual que en todos los lenguajes.

## Slide 10
layout: two-column
Title: JavaScript y Python
Left: fetch con header / X-API-Key, respuesta / JSON directa
Right: requests con header / X-API-Key, respuesta / JSON directa
Brief: Dos paneles que muestran la misma llamada en los dos lenguajes del equipo: fetch y requests. El header es el mismo en ambos.
Notes: En frontend se usa fetch con el header X-API-Key; en scripts de Python, requests. Ambos reciben el mismo JSON plano.

## Slide 11
layout: composed
Title: Filtros disponibles
Brief: Una tabla de consulta: el filtro, un ejemplo y qué filtra. Los valores son el punto, por eso tabla, no imagen.
Block: table
Filtro | Ejemplo | Qué filtra
almacen | ?almacen=S5 | almacén, auto-detecta sucursales
search | ?search=crackcito | SKU o descripción
linea | ?linea=PELOTAS | por ID (01) o nombre
categoria | ?categoria=VINIFAN | VINIBALL, VINIFAN, industrial
tipo | ?tipo=mktd | venta o mktd
fuente | ?fuente=todas | general, sucursales o todas
limit | ?limit=50 | máximo 5000 items
Notes: Los filtros se combinan entre sí. almacen auto-detecta las sucursales; search recorre SKU y descripción; limit corta la respuesta y su máximo es 5000.

## Slide 12
layout: composed
Title: La ficha de un SKU
Brief: La misma forma de la respuesta se explica campo por campo, con el ejemplo real de 02217. Código y valor alineados.
Block: table
Campo | Ejemplo | Qué es
sku | 02217 | código del producto
descripcion | FORRO N VINIFAN OFICIO CRISTAL 27 | nombre
almacenes | VES 63.400 · 40 7.000 | stock por bodega
precio | 10.25 | precio de venta
ean13 | 7754807020015 | código de barras
un_bx | 25 | unidades por caja
sin_catalogo | false | fuera del catálogo maestral
Notes: La respuesta de un SKU trae identidad, stock por almacén y atributos comerciales. sin_catalogo marca los productos que no están en el catálogo maestral.

## Slide 13
layout: composed
Title: Almacenes disponibles
Brief: Dos bloques, venta y marketing, cada uno con sus bodegas. La comparación importa porque el tipo define qué lista pides con tipo=.
Block: comparison
! Venta | VES, 40, 92, 106, 121, 122, 129
Marketing | 118, S1, S2, S3, S5, S6, S9, S11, S13, S14, S15, S16, S17
Notes: Los almacenes se agrupan por negocio. Para listar stock de venta se filtra con tipo=venta; para marketing, con tipo=mktd, que incluye la 118 y las bodegas S*.

## Slide 14
layout: composed
Title: Antes de escribir código
Brief: Cuatro números y reglas que evitan una pregunta al repasar código: límite, cache, vigencia y horario. El lead es el rate limit.
Block: stat-row
60 | requests por minuto / por IP
10 min | TTL del cache de stock
cache_expirado | true = datos / desactualizados
Lun-Sáb 7:00-22:59 | actualización, / hora Lima
Notes: La API limita a 60 peticiones por minuto por IP. El stock se cachea 10 minutos y el catálogo 6 horas. cache_expirado:true avisa de datos previos al último refresco. La actualización corre de lunes a sábado de 7:00 a 22:59.

## Slide 15
layout: title
Canvas: ink
Title: Listo para consultar
Subtitle: Swagger /docs · Repositorio github.com/carloscus/g360-stock-api · v1.4.0
Brief: Cierre claro que devuelve la atención a los recursos: el Swagger, el repo y la versión vigente del manual.
Notes: El manual termina con las tres rutas útiles: la documentación interactiva, el repositorio del servicio y la versión vigente (1.4.0).