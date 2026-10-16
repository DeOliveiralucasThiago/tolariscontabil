"""Planejado × realizado e projeção de limites do cliente."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..acompanhamento_servico import analisar, carregar_series, plano_do_cliente
from ..db import get_db
from ..models import Usuario
from ..seguranca import usuario_atual
from .clientes import obter_cliente

router = APIRouter(tags=["acompanhamento"])


@router.get("/clientes/{cliente_id}/acompanhamento")
def acompanhamento(cliente_id: int, usuario: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)) -> dict[str, Any]:
    cliente = obter_cliente(db, usuario, cliente_id)
    series = carregar_series(db, usuario.escritorio_id, cliente.id).get(cliente.id)
    return analisar(cliente, plano_do_cliente(db, cliente.id), series)
