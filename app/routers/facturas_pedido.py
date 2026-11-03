from datetime import datetime
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..acceso import cliente_restringido
from ..database import get_db
from ..models import FacturaPedido
from ..schemas import FacturaPedidoLeer

router = APIRouter(prefix="/facturas-pedido", tags=["Facturas por pedido"])


@router.get("/", response_model=List[FacturaPedidoLeer])
def listar(
    cliente_id: Optional[UUID] = None,
    desde: Optional[datetime] = None,
    hasta: Optional[datetime] = None,
    estado: Optional[str] = None,
    limite: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    propio: Optional[UUID] = Depends(cliente_restringido),
):
    consulta = db.query(FacturaPedido)
    if propio:
        cliente_id = propio
    if cliente_id:
        consulta = consulta.filter(FacturaPedido.cliente_id == cliente_id)
    if desde:
        consulta = consulta.filter(FacturaPedido.emitida_en >= desde)
    if hasta:
        consulta = consulta.filter(FacturaPedido.emitida_en <= hasta)
    if estado:
        consulta = consulta.filter(FacturaPedido.estado == estado)
    return consulta.order_by(FacturaPedido.emitida_en.desc(), FacturaPedido.id).offset(offset).limit(limite).all()


@router.get("/envio/{envio_id}", response_model=FacturaPedidoLeer)
def factura_de_envio(envio_id: UUID, db: Session = Depends(get_db), propio: Optional[UUID] = Depends(cliente_restringido)):
    f = db.query(FacturaPedido).filter(FacturaPedido.envio_id == envio_id).first()
    if f is None or (propio and f.cliente_id != propio):
        raise HTTPException(status_code=404, detail="Ese pedido no tiene factura")
    return f


@router.get("/{factura_id}", response_model=FacturaPedidoLeer)
def obtener(factura_id: UUID, db: Session = Depends(get_db), propio: Optional[UUID] = Depends(cliente_restringido)):
    f = db.query(FacturaPedido).filter(FacturaPedido.id == factura_id).first()
    if f is None or (propio and f.cliente_id != propio):
        raise HTTPException(status_code=404, detail="Factura no encontrada")
    return f
