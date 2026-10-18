"""Propiedad de los datos: el gateway envía X-Cliente-Id cuando quien consulta es una cuenta de cliente."""
from typing import Optional
from uuid import UUID

from fastapi import Header, HTTPException


def cliente_restringido(x_cliente_id: Optional[str] = Header(default=None)) -> Optional[UUID]:
    """None = sin restricción (personal o llamada interna). UUID = solo puede ver lo de ese cliente."""
    if not x_cliente_id:
        return None
    try:
        return UUID(x_cliente_id)
    except ValueError:
        raise HTTPException(status_code=403, detail={"codigo": "SIN_PERMISO", "mensaje": "Identidad de cliente no válida"})
