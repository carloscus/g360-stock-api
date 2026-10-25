---
deck: g360-stock-api
audience: Equipo técnico y de negocio de CIPSA que consume la API de stock
register: presented
---

## Slide 1
layout: title
Title: g360-stock-api
Subtitle: API REST para datos de stock · Ecosistema G360 · CIPSA
Brief: Portada del proyecto con título y subtítulo descriptivo

## Slide 2
layout: statement
Canvas: ink
Statement: Un solo punto de verdad
Notes: Antes cada app consultaba el ERP directamente. Ahora hay una API centralizada que sirve stock enriquecido a todo el ecosistema.

## Slide 3
layout: title-content
Title: El problema
Body:
- Reportes de stock dispersos en el ERP
- Cada app hacía sus propias consultas
- Sin consistencia entre consumidores
- Sin performance optimizada

## Slide 4
layout: title-content
Title: La solución
Body:
Una API REST que centraliza el stock, lo enriquece con el catálogo maestro y lo sirve a todas las apps del ecosistema.

## Slide 5
layout: composed
Title: Arquitectura
Block: process
ERP (appweb) | Reportes XLS
↓
Stock API | FastAPI + Uvicorn
↓
Consumidores | Dashboard, reportes, apps

## Slide 6
layout: composed
Title: Fuentes de datos
Block: card-grid
Fuente general | VES, 40, 92, 121...
Fuente sucursales | S1, S2, S3... S17
Catálogo maestro | 3553 SKUs desde GitHub

## Slide 7
layout: composed
Title: Endpoints principales
Block: table
Endpoint | Descripción
GET /stock | Listar con filtros
GET /stock/{sku} | Ficha individual
GET /stock/skus | Universo compacto
GET /catalog | Catálogo maestro

## Slide 8
layout: composed
Title: Campo a campo
Block: stat-row
3553 | SKUs en catálogo
2227 | SKUs servidos
20 | Almacenes consolidados
10min | TTL stock

## Slide 9
layout: title-content
Title: Protecciones
Body:
- Rate limiting: 150 req/min global
- Circuit breaker: 3 fallos → 5 min pausa
- Cache con TTL: 10 min stock, 6h catálogo
- Reintentos con backoff ante caídas del ERP

## Slide 10
layout: title-content
Title: Ecosistema
Body:
11+ repos consumen la API: pedido-vigencias, ventas-pulse, stock-reporter, y más. Cada uno con su configuración propia.

## Slide 11
layout: title-content
Title: Roadmap futuro
Body:
- Descuentos desde SKU_PRECIOS.xlsx
- Medidas de caja (largo/ancho/alto)
- Mypy estricto
- Cache HTTP estratégico por SKU

## Slide 12
layout: statement
Canvas: accent
Statement: github.com/carloscus/g360-stock-api
Notes: Documentación interactiva en /docs · Versión 1.7.0
