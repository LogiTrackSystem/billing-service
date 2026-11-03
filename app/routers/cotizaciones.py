from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..acceso import cliente_restringido
from ..database import get_db
from ..models import Cotizacion
from ..schemas import CotizacionLeer, CotizacionSolicitud
from ..tarifa_pedido import calcular_monto

router = APIRouter(prefix="/cotizaciones", tags=["Cotizaciones"])


@router.post("/calcular", status_code=201)
def calcular(payload: CotizacionSolicitud, db: Session = Depends(get_db)):
    """Calcula y registra el precio de un pedido (uso interno: lo invoca Shipment en
    POST /envios/cotizar y al crear el envío para verificar el precio aceptado)."""
    c = calcular_monto(payload.peso_kg, payload.distancia_km)
    cot = Cotizacion(
        cliente_id=payload.cliente_id, peso_kg=payload.peso_kg, distancia_km=payload.distancia_km,
        monto_cop=c["monto_cop"], moneda=c["moneda"], base_cop=c["base_cop"], variable_cop=c["variable_cop"],
        minimo_cop=c["minimo_cop"], aplico_minimo=c["aplico_minimo"],
    )
    db.add(cot)
    db.commit()
    db.refresh(cot)
    return {
        "cotizacion_id": str(cot.id),
        "monto_cop": float(c["monto_cop"]),
        "moneda": c["moneda"],
        "desglose": {
            "base_cop": float(c["base_cop"]),
            "toneladas": float(c["toneladas"]),
            "distancia_km": float(c["distancia_km"]),
            "cop_por_ton_km": float(c["cop_por_ton_km"]),
            "variable_cop": float(c["variable_cop"]),
            "minimo_cop": float(c["minimo_cop"]),
            "aplico_minimo": c["aplico_minimo"],
        },
    }


@router.get("/", response_model=List[CotizacionLeer])
def listar(
    cliente_id: Optional[UUID] = None,
    limite: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    propio: Optional[UUID] = Depends(cliente_restringido),
):
    consulta = db.query(Cotizacion)
    if propio:
        cliente_id = propio
    if cliente_id:
        consulta = consulta.filter(Cotizacion.cliente_id == cliente_id)
    return consulta.order_by(Cotizacion.creado_en.desc()).limit(limite).all()


@router.get("/{cotizacion_id}", response_model=CotizacionLeer)
def obtener(cotizacion_id: UUID, db: Session = Depends(get_db), propio: Optional[UUID] = Depends(cliente_restringido)):
    cot = db.query(Cotizacion).filter(Cotizacion.id == cotizacion_id).first()
    if cot is None or (propio and cot.cliente_id != propio):
        raise HTTPException(status_code=404, detail="Cotización no encontrada")
    return cot
