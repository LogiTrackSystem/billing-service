# Billing Service

Microservicio de facturación y costes. Consume `shipment.delivered` (publicado por Shipment Service), calcula el coste simulado de la ruta asociada (combustible, peajes y horas de conductor estimados a partir de la distancia, consultada por REST a Routing Service) y acumula el monto correspondiente en la factura abierta del cliente para el período actual, según el modelo de tarifa configurado (`por_km`, `por_envio` o `tarifa_plana`).

No hay integración real con sistemas de peajes/combustible ni con un ERP de facturación — los costes se simulan a partir de la distancia de la ruta, y el cierre de facturación es manual (`POST /facturas/cerrar-periodo`) en vez de un job automático, ya que el proyecto no tiene infraestructura de scheduling.

## Requisitos

- Python 3.11+
- PostgreSQL
- RabbitMQ
- Shipment Service corriendo (para obtener el `cliente_id` de un envío)
- Routing Service corriendo (para obtener la `distancia_km` de la ruta asociada)

## Setup

1. Crear la base de datos `billing_db`.
2. Copiar `.env.example` a `.env` y completar con tus credenciales reales.
3. `python -m venv venv && venv\Scripts\activate`
4. `pip install -r requirements.txt`
5. `alembic upgrade head`
6. `uvicorn app.main:app --reload --port 8008`

## Endpoints

- `POST /tarifas/` — configura o actualiza el modelo de tarifa de un cliente (`por_km`, `por_envio`, `tarifa_plana`).
- `GET /tarifas/{cliente_id}` — consulta la tarifa configurada de un cliente.
- `GET /costos-ruta/` — lista los costos simulados por ruta (filtro opcional por `envio_id`).
- `GET /facturas/` — lista facturas (filtros opcionales por `cliente_id`, `periodo`, `estado`).
- `GET /facturas/{id}` — obtiene una factura puntual.
- `POST /facturas/cerrar-periodo` — cierra manualmente las facturas abiertas del período actual y genera las de clientes con tarifa plana.
- `GET /health` — healthcheck.

## Eventos

- **Consume:** `shipment.delivered`
- **Publica:** ninguno (es un servicio terminal, sin consumidores posteriores definidos en el PDF)

---

<!-- entrega-final -->

## Descripción

Cotizaciones, pagos simulados, facturas por pedido, reembolsos, costos de ruta y tarifas por cliente.

- **Puerto local:** 8008   ·   **Despliegue activo:** <https://logitrack-billing.onrender.com> (`/health` y `/metrics` públicos)
- **Imagen Docker:** `<usuario-dockerhub>/logitrack-billing`   ·   **Repositorio de CI/CD:** `LogiTrackSystem/pipelines`

## Variables de entorno

Copia `.env.example` como `.env` y completa los valores. El `.env` **no se sube** al repositorio.

| Variable | Para qué sirve |
|---|---|
| `DATABASE_URL` | Conexión a la base PostgreSQL del servicio (`postgresql://usuario:clave@host:5432/<base>`). Es un secreto. |
| `RABBITMQ_URL` | URL AMQP del bus de eventos RabbitMQ (CloudAMQP en producción). Es un secreto. |
| `SHIPMENT_SERVICE_URL` | URL base de Shipment Service, sin barra final (en local `http://localhost:<puerto>`). |
| `ROUTING_SERVICE_URL` | URL base de Routing Service, sin barra final (en local `http://localhost:<puerto>`). |
| `TARIFA_MINIMA_COP` | Precio mínimo de un pedido en COP (valor de ejemplo, opcional). |
| `TARIFA_BASE_COP` | Cargo base de un pedido en COP (valor de ejemplo, opcional). |
| `TARIFA_COP_POR_TON_KM` | Tarifa en COP por tonelada y kilómetro (valor de ejemplo, opcional). |
| `INTERNAL_API_KEY` | Clave compartida entre el gateway y los servicios: exige la cabecera `X-Internal-Key` en todas las rutas salvo `/health` y `/metrics`. Vacía = sin restricción (solo local). Es un secreto. |

## Documentación de la API

- **Local** (sin `INTERNAL_API_KEY`): <http://localhost:8008/docs> (Swagger) y `http://localhost:8008/openapi.json`.
- **Producción:** el servicio solo atiende peticiones que llegan por el gateway (con `INTERNAL_API_KEY` activa su `/docs` no es público); la documentación de todas las rutas está en <https://logitrack-gateway.onrender.com/docs>.

## Base de datos

- Migraciones con Alembic (`alembic/`): `alembic upgrade head` (el `Dockerfile` ya lo ejecuta al arrancar).
- `db/esquema.sql`: esquema completo de `billing_db` generado desde las migraciones.
- Datos de ejemplo: este servicio se alimenta de eventos y llamadas de otros servicios; se generan ejecutando el flujo completo (por ejemplo `_pruebas/casos.py` del proyecto).
- Respaldo y restauración: ver `db/README.md`.

## Pruebas

Con el entorno virtual activo y `pip install -r requirements-dev.txt`:

```
pytest tests/unit                    # 2 pruebas unitarias
pytest tests/integration             # 1 prueba de integración
pytest --cov=app --cov-report=term   # toda la suite con cobertura
```

| Prueba | Qué verifica |
|---|---|
| Unitaria 1 | `tarifa_pedido.calcular_monto` |
| Unitaria 2 | `pedidos.registrar_cobro` |
| Integración | cobro de un pedido → pago y factura consultables por API |

Archivos: `tests/unit/` y `tests/integration/` (test_calcular_monto.py, test_registrar_cobro.py, test_flujo_cobro.py). Cobertura de `app/` medida: **≈ 77 %**; en cada push y Pull Request GitHub Actions la recalcula y guarda `coverage.xml` como artefacto (`cobertura-billing`).

## Métricas y monitoreo

Expone `GET /metrics` (formato Prometheus: `http_requests_total` y `http_request_duration_*`). Prometheus y el dashboard de Grafana están en el repositorio `logitrack-monitoring`.

## CI/CD

- `.github/workflows/pr.yml`: en cada push (rama distinta de `main`) y en cada Pull Request a `main` ejecuta el CI reutilizable (lint, pruebas con cobertura, `docker build` y prueba de arranque).
- `.github/workflows/deploy.yml`: al fusionar en `main`, y solo con las pruebas en verde, publica la imagen en Docker Hub y despliega en Render (con verificación de `/health` y rollback manual).
- Detalle y estrategia de ramas: `CICD.md` en el repositorio `LogiTrackSystem/pipelines`.

