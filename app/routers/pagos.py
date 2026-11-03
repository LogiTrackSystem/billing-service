from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Body, Depends, Header, HTTPException, Query
from sqlalchemy.orm import Session

from ..acceso import cliente_restringido
from ..database import get_db
from ..models import Pago, SolicitudReembolso
from ..reembolsos import ReembolsoError, ejecutar_reembolso
from ..schemas import PagoLeer, PagoPorReembolsar, ReembolsoCrear

router = APIRouter(prefix="/pagos", tags=["Pagos"])


@router.get("/", response_model=List[PagoLeer])
def listar(
    cliente_id: Optional[UUID] = None,
    estado: Optional[str] = None,
    envio_id: Optional[UUID] = None,
    limite: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    propio: Optional[UUID] = Depends(cliente_restringido),
):
    consulta = db.query(Pago)
    if propio:
        cliente_id = propio
    if cliente_id:
        consulta = consulta.filter(Pago.cliente_id == cliente_id)
    if estado:
        consulta = consulta.filter(Pago.estado == estado)
    if envio_id:
        consulta = consulta.filter(Pago.envio_id == envio_id)
    return consulta.order_by(Pago.creado_en.desc(), Pago.id).offset(offset).limit(limite).all()


@router.get("/por-reembolsar", response_model=List[PagoPorReembolsar])
def por_reembolsar(
    limite: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    propio: Optional[UUID] = Depends(cliente_restringido),
):
    """Pagos confirmados de pedidos cancelados o devueltos, a la espera de que un administrador los reembolse."""
    consulta = (
        db.query(Pago, SolicitudReembolso)
        .join(SolicitudReembolso, SolicitudReembolso.envio_id == Pago.envio_id)
        .filter(Pago.estado == "confirmado")
    )
    if propio:
        consulta = consulta.filter(Pago.cliente_id == propio)
    filas = consulta.order_by(SolicitudReembolso.registrada_en.asc(), Pago.id).offset(offset).limit(limite).all()
    return [
        PagoPorReembolsar.model_validate({
            **PagoLeer.model_validate(pago).model_dump(),
            "motivo": sol.motivo, "detalle": sol.detalle, "solicitado_en": sol.registrada_en,
        })
        for pago, sol in filas
    ]


@router.post("/{pago_id}/reembolsar", response_model=PagoLeer)
def reembolsar(
    pago_id: UUID,
    cuerpo: Optional[ReembolsoCrear] = Body(default=None),
    x_user_id: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    """Reembolso simulado de un pedido cancelado o devuelto: el pago pasa a 'reembolsado' y su factura a
    'anulada'. No mueve dinero real. El gateway solo deja pasar al administrador."""
    try:
        quien = UUID(x_user_id) if x_user_id else None
    except ValueError:
        quien = None
    try:
        return ejecutar_reembolso(db, pago_id, quien, cuerpo.nota if cuerpo else None)
    except ReembolsoError as e:
        raise HTTPException(status_code=e.status, detail={"codigo": e.codigo, "mensaje": e.mensaje})


@router.get("/envio/{envio_id}", response_model=PagoLeer)
def pago_de_envio(envio_id: UUID, db: Session = Depends(get_db), propio: Optional[UUID] = Depends(cliente_restringido)):
    pago = db.query(Pago).filter(Pago.envio_id == envio_id).first()
    if pago is None or (propio and pago.cliente_id != propio):
        raise HTTPException(status_code=404, detail="Ese pedido no tiene pago registrado")
    return pago


@router.get("/{pago_id}", response_model=PagoLeer)
def obtener(pago_id: UUID, db: Session = Depends(get_db), propio: Optional[UUID] = Depends(cliente_restringido)):
    pago = db.query(Pago).filter(Pago.id == pago_id).first()
    if pago is None or (propio and pago.cliente_id != propio):
        raise HTTPException(status_code=404, detail="Pago no encontrado")
    return pago
