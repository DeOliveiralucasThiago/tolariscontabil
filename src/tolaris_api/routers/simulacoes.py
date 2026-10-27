from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Cliente, Escritorio, Simulacao, Usuario
from ..pdf import gerar_proposta, nome_arquivo
from ..schemas import (
    CompletaEntrada,
    ExpressaEntrada,
    PainelSaida,
    ProspeccaoEntrada,
    ProspeccaoSaida,
    SimulacaoSaida,
)
from ..seguranca import usuario_atual
from decimal import Decimal

from ..impedimentos_servico import impedimentos_para_simulacao
from ..servicos import VERSAO_MOTOR, executar_completa, executar_expressa, titulo_simulacao
from .clientes import cliente_saida, obter_cliente

router = APIRouter(tags=["simulações"])


def _salvar(db: Session, usuario: Usuario, cliente: Cliente, tipo: str, entrada: Any, resultado: dict) -> Simulacao:
    sim = Simulacao(
        escritorio_id=usuario.escritorio_id,
        cliente=cliente,
        criado_por_id=usuario.id,
        tipo=tipo,
        titulo=titulo_simulacao(tipo, resultado),
        entrada=entrada.model_dump(mode="json"),
        resultado=resultado,
        versao_motor=VERSAO_MOTOR,
    )
    db.add(sim)
    return sim


def _com_natureza(dados: Any, cliente: Cliente) -> Any:
    """Leva a natureza jurídica e os impedimentos do Simples do cadastro para a simulação quando a tela não os informou."""
    mudancas: dict[str, Any] = {}
    if dados.natureza_juridica is None and cliente.natureza_juridica:
        mudancas["natureza_juridica"] = cliente.natureza_juridica
    if not dados.impedimentos_simples:
        receita = getattr(dados, "receita_bruta_anual", None)
        if receita is None:
            receita = dados.faturamento_mensal * 12
        impedimentos = impedimentos_para_simulacao(cliente, Decimal(receita))
        if impedimentos:
            mudancas["impedimentos_simples"] = impedimentos
    return dados.model_copy(update=mudancas) if mudancas else dados


def _obter_simulacao(db: Session, usuario: Usuario, simulacao_id: int) -> Simulacao:
    sim = db.get(Simulacao, simulacao_id)
    if sim is None or sim.escritorio_id != usuario.escritorio_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Simulação não encontrada")
    return sim


# --- Prévia (não salva) -----------------------------------------------------------
@router.post("/simulacoes/previa/expressa")
def previa_expressa(dados: ExpressaEntrada, _: Usuario = Depends(usuario_atual)) -> dict[str, Any]:
    return executar_expressa(dados)


@router.post("/simulacoes/previa/completa")
def previa_completa(dados: CompletaEntrada, _: Usuario = Depends(usuario_atual)) -> dict[str, Any]:
    return executar_completa(dados)


# --- Prospecção: cria/atualiza o prospect e salva a simulação expressa --------------
@router.post("/prospeccao", response_model=ProspeccaoSaida, status_code=status.HTTP_201_CREATED)
def prospeccao(
    dados: ProspeccaoEntrada, usuario: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)
) -> ProspeccaoSaida:
    cliente = None
    if dados.cliente.cnpj:
        cliente = db.scalar(
            select(Cliente).where(Cliente.escritorio_id == usuario.escritorio_id, Cliente.cnpj == dados.cliente.cnpj)
        )
    campos = dados.cliente.model_dump(exclude_unset=True)
    if cliente is None:
        cliente = Cliente(escritorio_id=usuario.escritorio_id, **dados.cliente.model_dump())
        db.add(cliente)
    else:
        campos.pop("status", None)  # não rebaixa um cliente ativo para prospect
        for campo, valor in campos.items():
            if valor is not None:
                setattr(cliente, campo, valor)
    if cliente.atividade is None:
        cliente.atividade = dados.simulacao.atividade.value
    simulacao = _com_natureza(dados.simulacao, cliente)
    sim = _salvar(db, usuario, cliente, "expressa", simulacao, executar_expressa(simulacao))
    db.commit()
    return ProspeccaoSaida(cliente=cliente_saida(db, cliente), simulacao=SimulacaoSaida.model_validate(sim))


# --- Simulações de um cliente --------------------------------------------------------
@router.get("/clientes/{cliente_id}/simulacoes", response_model=list[SimulacaoSaida])
def listar(cliente_id: int, usuario: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)) -> list[Simulacao]:
    return obter_cliente(db, usuario, cliente_id).simulacoes


@router.post(
    "/clientes/{cliente_id}/simulacoes/expressa", response_model=SimulacaoSaida, status_code=status.HTTP_201_CREATED
)
def salvar_expressa(
    cliente_id: int, dados: ExpressaEntrada, usuario: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)
) -> Simulacao:
    cliente = obter_cliente(db, usuario, cliente_id)
    dados = _com_natureza(dados, cliente)
    sim = _salvar(db, usuario, cliente, "expressa", dados, executar_expressa(dados))
    db.commit()
    return sim


@router.post(
    "/clientes/{cliente_id}/simulacoes/completa", response_model=SimulacaoSaida, status_code=status.HTTP_201_CREATED
)
def salvar_completa(
    cliente_id: int, dados: CompletaEntrada, usuario: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)
) -> Simulacao:
    cliente = obter_cliente(db, usuario, cliente_id)
    dados = _com_natureza(dados, cliente)
    sim = _salvar(db, usuario, cliente, "completa", dados, executar_completa(dados))
    db.commit()
    return sim


@router.get("/simulacoes/{simulacao_id}", response_model=SimulacaoSaida)
def detalhar(simulacao_id: int, usuario: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)) -> Simulacao:
    return _obter_simulacao(db, usuario, simulacao_id)


@router.delete("/simulacoes/{simulacao_id}", status_code=status.HTTP_204_NO_CONTENT)
def excluir(simulacao_id: int, usuario: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)) -> None:
    db.delete(_obter_simulacao(db, usuario, simulacao_id))
    db.commit()


@router.get("/simulacoes/{simulacao_id}/proposta.pdf")
def proposta_pdf(simulacao_id: int, usuario: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)) -> Response:
    sim = _obter_simulacao(db, usuario, simulacao_id)
    escritorio = db.get(Escritorio, usuario.escritorio_id)
    pdf = gerar_proposta(escritorio, sim.cliente, sim, usuario)
    nome = nome_arquivo(sim)
    return Response(pdf, media_type="application/pdf", headers={"Content-Disposition": f'inline; filename="{nome}"'})


# --- Painel ---------------------------------------------------------------------
@router.get("/painel", response_model=PainelSaida)
def painel(usuario: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)) -> PainelSaida:
    esc = usuario.escritorio_id
    contagem = dict(
        db.execute(
            select(Cliente.status, func.count()).where(Cliente.escritorio_id == esc).group_by(Cliente.status)
        ).all()
    )
    agora = datetime.now(timezone.utc)
    inicio_mes = agora.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    do_mes = db.scalars(
        select(Simulacao)
        .where(Simulacao.escritorio_id == esc, Simulacao.criado_em >= inicio_mes)
        .order_by(Simulacao.criado_em)
    ).all()
    # Economia identificada: só a simulação mais recente de cada cliente (sem contar o mesmo cliente duas vezes)
    ultima_por_cliente = {s.cliente_id: s for s in do_mes}
    ultimas = db.execute(
        select(Simulacao, Cliente.razao_social)
        .join(Cliente, Cliente.id == Simulacao.cliente_id)
        .where(Simulacao.escritorio_id == esc)
        .order_by(Simulacao.criado_em.desc())
        .limit(8)
    ).all()
    return PainelSaida(
        clientes_ativos=contagem.get("ativo", 0),
        prospects=contagem.get("prospect", 0),
        simulacoes_mes=len(do_mes),
        economia_identificada_mes=round(
            sum(s.resultado.get("economia_vs_pior", 0) for s in ultima_por_cliente.values()), 2
        ),
        ultimas_simulacoes=[
            {
                "id": s.id,
                "cliente_id": s.cliente_id,
                "cliente": nome,
                "titulo": s.titulo,
                "melhor": s.resultado.get("melhor"),
                "economia": s.resultado.get("economia_vs_pior"),
                "criado_em": s.criado_em.isoformat(),
            }
            for s, nome in ultimas
        ],
    )
