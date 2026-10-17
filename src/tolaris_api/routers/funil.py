"""Funil comercial do escritório: propostas de honorários da criação ao aceite."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..db import get_db
from ..funil_servico import montar
from ..models import Usuario
from ..seguranca import usuario_atual

router = APIRouter(tags=["funil comercial"])


@router.get("/funil")
def funil(
    dias: int = Query(default=90, ge=0, le=3650, description="Só propostas criadas nos últimos N dias; 0 = todas"),
    usuario: Usuario = Depends(usuario_atual),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return montar(db, usuario.escritorio_id, dias or None)
