"""Conferência dos impedimentos do Simples de um cliente: perguntas, respostas guardadas, achados e o que vai para as simulações."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from tolaris_motor import impedimentos as motor
from tolaris_motor import natureza_juridica

from .cnpj import classificar_cnaes
from .models import Cliente


def respostas_do_cliente(cliente: Cliente) -> tuple[dict[str, bool | None], Decimal | None]:
    dados = cliente.impedimentos_simples or {}
    respostas = {k: v for k, v in (dados.get("respostas") or {}).items() if k in motor.POR_CHAVE and v in (True, False, None)}
    outras = dados.get("receita_outras_empresas")
    return respostas, (Decimal(str(outras)) if outras is not None else None)


def achados_do_cliente(cliente: Cliente, receita_propria: Decimal | None) -> list[motor.Achado]:
    respostas, outras = respostas_do_cliente(cliente)
    return motor.avaliar(respostas, receita_propria or Decimal(0), outras if receita_propria is not None else None)


def impedimentos_para_simulacao(cliente: Cliente, receita_propria: Decimal) -> list[str]:
    """Textos dos impedimentos confirmados (e já certos com a receita da simulação) para o cálculo do Simples."""
    return motor.textos_que_impedem(achados_do_cliente(cliente, receita_propria))


def resumo(cliente: Cliente) -> dict[str, int]:
    """Contagem para o cabeçalho do cliente (sem receita: os impedimentos que dependem dela contam como "dependem")."""
    respostas, outras = respostas_do_cliente(cliente)
    achados = motor.avaliar(respostas, Decimal(0), None)
    return {
        "impedem": sum(1 for a in achados if a.status == "impede"),
        "dependem": sum(1 for a in achados if a.status == "depende_da_receita"),
        "pendentes": len(motor.pendentes(respostas)),
        "total": len(motor.PERGUNTAS),
    }


def conferencia(cliente: Cliente, receita_propria: Decimal | None = None) -> dict[str, Any]:
    """O que a tela mostra: perguntas por grupo com a resposta, achados, verificações automáticas e se o Simples é possível."""
    respostas, outras = respostas_do_cliente(cliente)
    achados = achados_do_cliente(cliente, receita_propria)
    grupos: dict[str, list[dict[str, Any]]] = {}
    for p in motor.PERGUNTAS:
        grupos.setdefault(p.grupo, []).append({
            "chave": p.chave, "texto": p.texto, "base_legal": p.base_legal, "ajuda": p.ajuda,
            "depende_da_receita_global": p.depende_da_receita_global, "resposta": respostas.get(p.chave),
        })
    automaticos = []
    natureza = natureza_juridica.classificar(cliente.natureza_juridica, cliente.natureza_juridica_codigo)
    if natureza_juridica.impede_simples(natureza):
        automaticos.append({"origem": "Natureza jurídica", "texto": f"{natureza.rotulo}: {natureza.explicacao}", "base_legal": natureza_juridica.BASE_LEGAL_ELEGIBILIDADE})
    cnaes = classificar_cnaes(cliente.cnae_principal, cliente.cnae_descricao, cliente.cnaes_secundarios, cliente.atividade)
    for c in cnaes["vedados"]:
        ambiguo = c.get("vedacao") == "ambiguo"
        automaticos.append({
            "origem": "CNAE do cadastro",
            "texto": f"{c['codigo']} {c['descricao']}: {'CNAE que abrange atividade permitida e atividade vedada; confira o que a empresa faz' if ambiguo else 'atividade vedada ao Simples'}",
            "base_legal": "Res. CGSN 140/2018, Anexos VI e VII",
        })
    impedem = [a for a in achados if a.status == "impede"]
    bloqueado = bool(impedem) or any(a["origem"] == "Natureza jurídica" for a in automaticos)
    return {
        "grupos": [{"grupo": g, "perguntas": ps} for g, ps in grupos.items()],
        "receita_outras_empresas": float(outras) if outras is not None else None,
        "achados": [{"chave": a.chave, "status": a.status, "texto": a.texto, "base_legal": a.base_legal} for a in achados],
        "automaticos": automaticos,
        "pendentes": len(motor.pendentes(respostas)),
        "total": len(motor.PERGUNTAS),
        "limite_receita_global": float(motor.LIMITE_RECEITA_GLOBAL),
        "simples_possivel": False if bloqueado else (None if (any(a.status == "depende_da_receita" for a in achados) or motor.pendentes(respostas)) else True),
    }
