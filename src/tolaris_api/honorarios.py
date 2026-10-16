"""Honorários do escritório: sugestão pelo regime recomendado e pelo número de funcionários, e a proposta
que fica anexada à simulação (aparece no PDF e no portal do cliente)."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from tolaris_motor.base import arredondar

from .acesso import agora
from .schemas import HonorariosConfig, HonorariosEntrada

FUSO = ZoneInfo("America/Sao_Paulo")
VALIDADE_PADRAO_DIAS = 15


def hoje() -> date:
    return datetime.now(FUSO).date()


def chave_do_regime(melhor: str | None) -> str | None:
    """Regime recomendado ("Simples Nacional", "Lucro Presumido"...) na chave usada pela tabela de honorários."""
    texto = (melhor or "").lower()
    if texto.startswith("mei"):
        return "mei"
    for chave, trecho in (("simples", "simples"), ("presumido", "presumido"), ("real", "lucro real")):
        if trecho in texto:
            return chave
    return None


def config_para_banco(c: HonorariosConfig) -> dict[str, Any]:
    return {
        "base": {k: float(arredondar(v)) for k, v in c.base.items()},
        "por_funcionario": float(arredondar(c.por_funcionario)),
        "adesao": float(arredondar(c.adesao)),
        "servicos": c.servicos.strip(),
        "validade_dias": c.validade_dias,
    }


def sugerir(config: dict[str, Any] | None, melhor: str | None, funcionarios: int) -> dict[str, Any]:
    """Valor sugerido = base do regime recomendado + adicional por funcionário. Sem tabela, vem zerado."""
    cfg = config or {}
    chave = chave_do_regime(melhor)
    base = Decimal(str((cfg.get("base") or {}).get(chave, 0))) if chave else Decimal(0)
    por_funcionario = Decimal(str(cfg.get("por_funcionario", 0)))
    return {
        "configurado": bool(cfg),
        "regime": chave,
        "base": float(base),
        "por_funcionario": float(por_funcionario),
        "funcionarios": funcionarios,
        "valor_mensal": float(arredondar(base + por_funcionario * funcionarios)),
        "adesao": float(cfg.get("adesao", 0)),
        "servicos": cfg.get("servicos", ""),
        "validade_dias": int(cfg.get("validade_dias", VALIDADE_PADRAO_DIAS)),
    }


def montar(config: dict[str, Any] | None, melhor: str | None, e: HonorariosEntrada) -> dict[str, Any]:
    """Proposta a gravar na simulação. Campos não informados vêm da sugestão (tabela do escritório)."""
    s = sugerir(config, melhor, e.funcionarios)
    valor = e.valor_mensal if e.valor_mensal is not None else Decimal(str(s["valor_mensal"]))
    if valor <= 0:
        raise ValueError("Informe o valor mensal dos honorários (ou preencha a tabela de honorários nas Configurações).")
    adesao = e.adesao if e.adesao is not None else Decimal(str(s["adesao"]))
    validade = e.validade_dias or s["validade_dias"]
    return {
        "funcionarios": e.funcionarios,
        "valor_mensal": float(arredondar(valor)),
        "adesao": float(arredondar(adesao)),
        "servicos": (e.servicos if e.servicos is not None else s["servicos"]).strip(),
        "validade_dias": validade,
        "definido_em": agora().isoformat(),
        "valido_ate": (hoje() + timedelta(days=validade)).isoformat(),
    }


def expirada(h: dict[str, Any]) -> bool:
    return date.fromisoformat(h["valido_ate"]) < hoje()


def total_primeiro_ano(h: dict[str, Any]) -> float:
    return round(h["valor_mensal"] * 12 + h.get("adesao", 0), 2)


def para_pdf(h: dict[str, Any], economia_anual: float | None, aceite_em: datetime | None, aceite_nome: str | None) -> dict[str, Any]:
    """Números e textos que o PDF mostra na seção de honorários."""
    total = total_primeiro_ano(h)
    economia = float(economia_anual or 0)
    razao = round(economia / total, 1) if total > 0 and economia > 0 else None
    aceite = None
    if aceite_em is not None:
        quando = aceite_em if aceite_em.tzinfo else aceite_em.replace(tzinfo=agora().tzinfo)
        aceite = {"nome": aceite_nome, "quando": quando.astimezone(FUSO).strftime("%d/%m/%Y às %H:%M")}
    return {
        **h,
        "anual": round(h["valor_mensal"] * 12, 2),
        "total_primeiro_ano": total,
        "economia": economia if economia > 0 else None,
        "razao": razao if razao and razao >= 1 else None,
        "valido_ate_br": date.fromisoformat(h["valido_ate"]).strftime("%d/%m/%Y"),
        "linhas_servicos": [x.strip() for x in h.get("servicos", "").splitlines() if x.strip()],
        "aceite": aceite,
    }


def para_portal(h: dict[str, Any]) -> dict[str, Any]:
    """O que o cliente vê da proposta no portal."""
    return {
        "valor_mensal": h["valor_mensal"],
        "adesao": h.get("adesao", 0),
        "servicos": h.get("servicos", ""),
        "valido_ate": h["valido_ate"],
        "expirada": expirada(h),
    }
