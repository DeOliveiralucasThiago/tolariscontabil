"""Central de avisos da carteira, mudanças na legislação e recálculo de simulações com as regras atuais."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..avisos_servico import mudancas, resumo_da_mudanca, reunir
from ..db import get_db
from ..models import Cliente, Simulacao, Usuario
from ..recuperacao_servico import analisar
from ..schemas import RecuperacaoEntrada, SimulacaoSaida
from ..seguranca import usuario_atual
from ..servicos import VERSAO_MOTOR, diferencas, pode_recalcular, recalcular_resultado, titulo_simulacao

router = APIRouter(tags=["avisos"])


@router.get("/avisos")
def listar_avisos(usuario: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)) -> dict[str, Any]:
    return reunir(db, usuario.escritorio_id)


@router.get("/mudancas")
def listar_mudancas(_: Usuario = Depends(usuario_atual)) -> list[dict[str, Any]]:
    return mudancas()


@router.post("/simulacoes/{simulacao_id}/recalcular", response_model=SimulacaoSaida, status_code=status.HTTP_201_CREATED)
def recalcular(simulacao_id: int, usuario: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)) -> Simulacao:
    """Cria uma nova simulação com a mesma entrada e as regras atuais; a original fica no histórico."""
    antiga = db.get(Simulacao, simulacao_id)
    if antiga is None or antiga.escritorio_id != usuario.escritorio_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Simulação não encontrada")
    if antiga.tipo == "recuperacao":
        cliente = db.get(Cliente, antiga.cliente_id)
        resultado = analisar(db, cliente, antiga.entrada.get("anexo"))
        if not resultado["disponivel"]:
            raise HTTPException(status.HTTP_409_CONFLICT, "O cliente não tem mais itens de notas importados")
        entrada = RecuperacaoEntrada(
            anexo=resultado["anexo"], periodo_inicio=resultado["periodo"]["inicio"], periodo_fim=resultado["periodo"]["fim"]
        ).model_dump(mode="json")
    elif pode_recalcular(antiga.tipo):
        try:
            resultado = recalcular_resultado(antiga.tipo, antiga.entrada)
        except Exception as erro:  # noqa: BLE001
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY, "Os dados desta simulação não servem mais ao cálculo atual"
            ) from erro
        entrada = dict(antiga.entrada)
    else:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Este tipo de relatório não pode ser recalculado")
    resultado["recalculo"] = {
        "de": antiga.id,
        "em": datetime.now(timezone.utc).isoformat(),
        "antes": {"melhor": antiga.resultado.get("melhor"), "economia_vs_pior": antiga.resultado.get("economia_vs_pior")},
        "resumo": resumo_da_mudanca(antiga.resultado, resultado, diferencas(antiga.resultado, resultado))
        if antiga.tipo != "recuperacao" else None,
    }
    nova = Simulacao(
        escritorio_id=usuario.escritorio_id,
        cliente_id=antiga.cliente_id,
        criado_por_id=usuario.id,
        tipo=antiga.tipo,
        titulo=titulo_simulacao(antiga.tipo, resultado),
        entrada=entrada,
        resultado=resultado,
        versao_motor=VERSAO_MOTOR,
    )
    db.add(nova)
    db.commit()
    return nova
