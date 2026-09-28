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