import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from .interno import proteger_servicio

from .routers import tarifas, costos_ruta, facturas, cotizaciones, pagos, facturas_pedido
from .events import iniciar_consumidor


@asynccontextmanager
async def lifespan(app: FastAPI):
    connection = await iniciar_consumidor()
    yield
    await connection.close()


app = FastAPI(title="Billing Service", lifespan=lifespan)
proteger_servicio(app)
app.include_router(tarifas.router)
app.include_router(costos_ruta.router)
app.include_router(facturas.router)
app.include_router(cotizaciones.router)
app.include_router(pagos.router)
app.include_router(facturas_pedido.router)


@app.get("/health")
def health():
    return {"status": "ok", "service": "billing-service", "version": os.getenv("APP_VERSION", "dev")}