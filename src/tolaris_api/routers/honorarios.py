"""Proposta de honorários anexada a uma simulação (aparece no PDF e no portal do cliente)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from ..db import get_db
from ..honorarios import montar, sugerir
from ..models import Escritorio, Simulacao, Usuario
from ..schemas import HonorariosEntrada, SimulacaoSaida
from ..seguranca import usuario_atual
from .simulacoes import _obter_simulacao

router = APIRouter(tags=["honorários"])

_JA_ACEITA = HTTPException(
    status.HTTP_409_CONFLICT, "Esta proposta já foi aceita pelo cliente e não pode mais ser alterada ou removida"
)


@router.get("/simulacoes/{simulacao_id}/honorarios/sugestao")
def sugestao(
    simulacao_id: int,
    funcionarios: int = Query(default=0, ge=0, le=10000),
    usuario: Usuario = Depends(usuario_atual),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    sim = _obter_simulacao(db, usuario, simulacao_id)
    esc = db.get(Escritorio, usuario.escritorio_id)
    return sugerir(esc.honorarios, sim.resultado.get("melhor"), funcionarios)


@router.put("/simulacoes/{simulacao_id}/honorarios", response_model=SimulacaoSaida)
def definir(
    simulacao_id: int, dados: HonorariosEntrada, usuario: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)
) -> Simulacao:
    sim = _obter_simulacao(db, usuario, simulacao_id)
    if sim.aceite_em is not None:
        raise _JA_ACEITA
    esc = db.get(Escritorio, usuario.escritorio_id)
    try:
        sim.honorarios = montar(esc.honorarios, sim.resultado.get("melhor"), dados)
    except ValueError as erro:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(erro)) from None
    db.commit()
    return sim


@router.delete("/simulacoes/{simulacao_id}/honorarios", status_code=status.HTTP_204_NO_CONTENT)
def remover(simulacao_id: int, usuario: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)) -> None:
    sim = _obter_simulacao(db, usuario, simulacao_id)
    if sim.aceite_em is not None:
        raise _JA_ACEITA
    sim.honorarios = None
    db.commit()
