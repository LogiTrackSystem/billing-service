from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import CostoRuta
from ..schemas import CostoRutaLeer

router = APIRouter(prefix="/costos-ruta", tags=["Costos de Ruta"])


@router.get("/", response_model=List[CostoRutaLeer])
def listar_costos(envio_id: Optional[UUID] = None, db: Session = Depends(get_db)):
    query = db.query(CostoRuta)
    if envio_id:
        query = query.filter(CostoRuta.envio_id == envio_id)
    return query.order_by(CostoRuta.creado_en.desc()).all()