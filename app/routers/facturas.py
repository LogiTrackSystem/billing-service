from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Factura, TarifaCliente
from ..schemas import FacturaLeer
from ..events import _periodo_actual

router = APIRouter(prefix="/facturas", tags=["Facturas"])


def _uuid_o_403(valor: str) -> UUID:
    try:
        return UUID(valor)
    except ValueError:
        raise HTTPException(status_code=403, detail={"codigo": "SIN_PERMISO", "mensaje": "Identidad de cliente no válida"})


@router.get("/", response_model=List[FacturaLeer])
def listar_facturas(
    cliente_id: Optional[UUID] = None,
    periodo: Optional[str] = None,
    estado: Optional[str] = None,
    db: Session = Depends(get_db),
    x_cliente_id: Optional[str] = Header(default=None),
):
    query = db.query(Factura)
    if x_cliente_id:  # lo envía el gateway para cuentas de cliente: solo ven lo suyo
        cliente_id = _uuid_o_403(x_cliente_id)
    if cliente_id:
        query = query.filter(Factura.cliente_id == cliente_id)
    if periodo:
        query = query.filter(Factura.periodo == periodo)
    if estado:
        query = query.filter(Factura.estado == estado)
    return query.order_by(Factura.periodo.desc()).all()


@router.get("/{factura_id}", response_model=FacturaLeer)
def obtener_factura(factura_id: UUID, db: Session = Depends(get_db), x_cliente_id: Optional[str] = Header(default=None)):
    factura = db.query(Factura).filter(Factura.id == factura_id).first()
    if factura is None or (x_cliente_id and factura.cliente_id != _uuid_o_403(x_cliente_id)):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Factura no encontrada")
    return factura


@router.post("/cerrar-periodo", response_model=List[FacturaLeer])
def cerrar_periodo(db: Session = Depends(get_db)):
    periodo = _periodo_actual()

    tarifas_planas = db.query(TarifaCliente).filter(TarifaCliente.modelo == "tarifa_plana").all()
    for tarifa in tarifas_planas:
        factura = (
            db.query(Factura)
            .filter(Factura.cliente_id == tarifa.cliente_id, Factura.periodo == periodo)
            .first()
        )
        if factura is None:
            factura = Factura(cliente_id=tarifa.cliente_id, periodo=periodo, monto_total=tarifa.valor, estado="abierta")
            db.add(factura)
        else:
            factura.monto_total = tarifa.valor
    db.commit()

    facturas_abiertas = db.query(Factura).filter(Factura.periodo == periodo, Factura.estado == "abierta").all()
    for factura in facturas_abiertas:
        factura.estado = "cerrada"
    db.commit()

    return db.query(Factura).filter(Factura.periodo == periodo).all()