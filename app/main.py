from contextlib import asynccontextmanager
from fastapi import FastAPI

from .routers import tarifas, costos_ruta, facturas, cotizaciones, pagos, facturas_pedido
from .events import iniciar_consumidor


@asynccontextmanager
async def lifespan(app: FastAPI):
    connection = await iniciar_consumidor()
    yield
    await connection.close()


app = FastAPI(title="Billing Service", lifespan=lifespan)
app.include_router(tarifas.router)
app.include_router(costos_ruta.router)
app.include_router(facturas.router)
app.include_router(cotizaciones.router)
app.include_router(pagos.router)
app.include_router(facturas_pedido.router)


@app.get("/health")
def health():
    return {"status": "ok", "service": "billing-service"}