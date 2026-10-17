"""Funil comercial: das propostas de honorários criadas até as aceitas.

Conta uma proposta por cliente (a mais recente): refazer a simulação de um cliente não infla o funil. Uma proposta
passa por criada, enviada (publicada no portal ou enviada por e-mail), vista (aberta pelo cliente no portal) e aceita;
as vencidas ficam à parte. Cada etapa conta também as propostas que já passaram dela.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .acesso import _aware, agora
from .avisos_servico import DIAS_NAO_VISTO, DIAS_SEM_RESPOSTA
from .honorarios import FUSO
from .models import Cliente, Envio, Simulacao

ETAPAS = ("criada", "enviada", "vista", "aceita")
ROTULOS = {
    "criada": "Propostas criadas",
    "enviada": "Enviadas ao cliente",
    "vista": "Abertas pelo cliente",
    "aceita": "Aceitas",
    "vencida": "Vencidas sem aceite",
}
ROTULO_ETAPA = {"criada": "Não enviada", "enviada": "Enviada", "vista": "Vista", "aceita": "Aceita", "vencida": "Vencida"}
DIAS_ALERTA_VENCIMENTO = 3


def _momento(v: datetime | None) -> datetime | None:
    return _aware(v) if v else None


def _dias(de: datetime, ate: datetime) -> int:
    return max(0, (ate - de).days)


def _proposta(s: Simulacao, c: Cliente, enviada_por_email: datetime | None, agora_: datetime, hoje: date) -> dict[str, Any]:
    h = s.honorarios
    definido = _momento(datetime.fromisoformat(h["definido_em"])) or _aware(s.criado_em)
    publicada = _momento(s.publicada_em) or (_aware(s.criado_em) if s.publicada else None)
    visto = _momento(s.visto_primeira_em)
    aceite = _momento(s.aceite_em)
    enviadas = [d for d in (publicada, _momento(enviada_por_email)) if d]
    enviada = min(enviadas) if enviadas else None
    if (visto or aceite) and enviada is None:
        enviada = visto or aceite  # abriu/aceitou o portal: foi enviada, mesmo sem registro da data
    valido_ate = date.fromisoformat(h["valido_ate"])
    if aceite:
        etapa = "aceita"
    elif valido_ate < hoje:
        etapa = "vencida"
    elif visto:
        etapa = "vista"
    elif enviada:
        etapa = "enviada"
    else:
        etapa = "criada"
    ultimo_evento = max(d for d in (definido, enviada, visto, aceite) if d)
    dias_parada = _dias(ultimo_evento, agora_)

    acao = None
    if etapa == "criada":
        acao = "Publique no portal ou envie por e-mail para o cliente ver."
    elif etapa == "enviada" and _dias(enviada, agora_) >= DIAS_NAO_VISTO:
        acao = f"Enviada há {_dias(enviada, agora_)} dias e ainda não aberta: lembre o cliente por WhatsApp ou e-mail."
    elif etapa == "vista" and _dias(visto, agora_) >= DIAS_SEM_RESPOSTA:
        acao = f"Vista há {_dias(visto, agora_)} dias sem resposta: vale um contato por telefone."
    elif etapa == "vencida":
        acao = "Venceu sem aceite: renove a proposta se ainda houver interesse."
    if etapa in ("criada", "enviada", "vista") and (valido_ate - hoje).days <= DIAS_ALERTA_VENCIMENTO:
        dias_validade = (valido_ate - hoje).days
        acao = (acao + " " if acao else "") + (f"Vence em {dias_validade} {'dia' if dias_validade == 1 else 'dias'}." if dias_validade > 0 else "Vence hoje.")

    economia = (s.resultado or {}).get("economia_vs_pior")
    return {
        "simulacao_id": s.id,
        "cliente_id": c.id,
        "cliente": c.razao_social,
        "cliente_status": c.status,
        "etapa": etapa,
        "rotulo_etapa": ROTULO_ETAPA[etapa],
        "valor_mensal": float(h["valor_mensal"]),
        "adesao": float(h.get("adesao", 0)),
        "criada_em": definido.isoformat(),
        "enviada_em": enviada.isoformat() if enviada else None,
        "visto_em": visto.isoformat() if visto else None,
        "aceite_em": aceite.isoformat() if aceite else None,
        "valido_ate": h["valido_ate"],
        "dias_parada": dias_parada,
        "acao": acao,
        "economia_anual": float(economia) if isinstance(economia, (int, float)) and economia > 0 else None,
        "_enviada": enviada, "_visto": visto, "_aceite": aceite, "_criada": definido,
    }


def _media(valores: list[float]) -> float | None:
    return round(sum(valores) / len(valores), 1) if valores else None


def montar(db: Session, escritorio_id: int, dias: int | None = None, hoje: date | None = None) -> dict[str, Any]:
    """Funil das propostas criadas nos últimos ``dias`` dias (None = todas)."""
    agora_ = agora()
    hoje = hoje or datetime.now(FUSO).date()
    envios = {
        sid: primeiro for sid, primeiro in db.execute(
            select(Envio.simulacao_id, func.min(Envio.criado_em)).where(Envio.escritorio_id == escritorio_id, Envio.status == "enviado")
            .group_by(Envio.simulacao_id)
        )
    }
    linhas = db.execute(
        select(Simulacao, Cliente).join(Cliente, Cliente.id == Simulacao.cliente_id)
        .where(Simulacao.escritorio_id == escritorio_id, Simulacao.honorarios.is_not(None))
        .order_by(Simulacao.id)
    ).all()
    por_cliente: dict[int, dict[str, Any]] = {}
    for s, c in linhas:  # em ordem de id: a última proposta do cliente fica
        if not s.honorarios or "valor_mensal" not in s.honorarios:
            continue
        por_cliente[c.id] = _proposta(s, c, envios.get(s.id), agora_, hoje)
    propostas = list(por_cliente.values())
    if dias:
        corte = agora_ - timedelta(days=dias)
        propostas = [p for p in propostas if p["_criada"] >= corte]

    def chegou(p: dict[str, Any], etapa: str) -> bool:
        """A proposta chegou a essa etapa (mesmo que tenha passado dela ou vencido depois)."""
        if etapa == "criada":
            return True
        if etapa == "enviada":
            return p["_enviada"] is not None
        if etapa == "vista":
            return p["_visto"] is not None or p["_aceite"] is not None
        return p["_aceite"] is not None

    funil = []
    anterior: int | None = None
    for etapa in ETAPAS:
        grupo = [p for p in propostas if chegou(p, etapa)]
        qtd = len(grupo)
        funil.append({
            "etapa": etapa,
            "rotulo": ROTULOS[etapa],
            "quantidade": qtd,
            "valor_mensal": round(sum(p["valor_mensal"] for p in grupo), 2),
            "conversao": None if anterior is None else (round(qtd / anterior, 4) if anterior else None),
        })
        anterior = qtd

    aceitas = [p for p in propostas if p["etapa"] == "aceita"]
    abertas = [p for p in propostas if p["etapa"] in ("criada", "enviada", "vista")]
    vencidas = [p for p in propostas if p["etapa"] == "vencida"]
    enviadas = [p for p in propostas if chegou(p, "enviada")]
    ate_visto = [(p["_visto"] - p["_enviada"]).total_seconds() / 86400 for p in propostas if p["_visto"] and p["_enviada"]]
    ate_aceite = [(p["_aceite"] - p["_enviada"]).total_seconds() / 86400 for p in aceitas if p["_enviada"]]
    resumo = {
        "propostas": len(propostas),
        "aceitas_valor_mensal": round(sum(p["valor_mensal"] for p in aceitas), 2),
        "aceitas_adesao": round(sum(p["adesao"] for p in aceitas), 2),
        "aceitas_primeiro_ano": round(sum(p["valor_mensal"] * 12 + p["adesao"] for p in aceitas), 2),
        "em_aberto": len(abertas),
        "em_aberto_valor_mensal": round(sum(p["valor_mensal"] for p in abertas), 2),
        "vencidas": len(vencidas),
        "vencidas_valor_mensal": round(sum(p["valor_mensal"] for p in vencidas), 2),
        "taxa_aceite": round(len(aceitas) / len(enviadas), 4) if enviadas else None,
        "dias_ate_visto": _media(ate_visto),
        "dias_ate_aceite": _media(ate_aceite),
        "economia_anual_aceitas": round(sum(p["economia_anual"] or 0 for p in aceitas), 2),
    }

    ordem = {"vista": 0, "enviada": 1, "criada": 2, "aceita": 3, "vencida": 4}
    propostas.sort(key=lambda p: (ordem[p["etapa"]], -p["valor_mensal"], p["cliente"].lower()))
    for p in propostas:
        for k in ("_enviada", "_visto", "_aceite", "_criada"):
            p.pop(k)
    return {"dias": dias, "funil": funil, "resumo": resumo, "propostas": propostas, "precisam_de_acao": sum(1 for p in propostas if p["acao"])}
