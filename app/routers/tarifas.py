from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import TarifaCliente
from ..schemas import TarifaClienteCrear, TarifaClienteLeer

router = APIRouter(prefix="/tarifas", tags=["Tarifas"])


@router.post("/", response_model=TarifaClienteLeer, status_code=status.HTTP_201_CREATED)
def configurar_tarifa(payload: TarifaClienteCrear, db: Session = Depends(get_db)):
    tarifa = db.query(TarifaCliente).filter(TarifaCliente.cliente_id == payload.cliente_id).first()
    if tarifa:
        tarifa.modelo = payload.modelo
        tarifa.valor = payload.valor
    else:
        tarifa = TarifaCliente(**payload.model_dump())
        db.add(tarifa)
    db.commit()
    db.refresh(tarifa)
    return tarifa


@router.get("/{cliente_id}", response_model=TarifaClienteLeer)
def obtener_tarifa(cliente_id: UUID, db: Session = Depends(get_db)):
    tarifa = db.query(TarifaCliente).filter(TarifaCliente.cliente_id == cliente_id).first()
    if tarifa is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="El cliente no tiene tarifa configurada (se usará 'por_envio' por defecto)")
    return tarifa