"""Aviso de prazo da opção pelo regime regular de IBS/CBS, para os clientes do Simples Nacional.

A empresa do Simples pode recolher IBS e CBS pelo regime regular (fora do DAS) a partir de 2027. A opção para janeiro a junho de 2027
vai de 01/09 a 30/10/2026 (Res. CGSN 186/2026, alterada pela 194/2026). O aviso mostra, para cada cliente, a partir de quanto de vendas
a empresas (B2B) compensa recolher por fora, calculado pelo Simples na Reforma de 2027 com a receita do cliente e sem compras com crédito.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from tolaris_motor import Atividade, PerfilEmpresa, avisos, brl, reforma_simples, simples

from .models import Cliente

PRAZO_OPCAO = date(2026, 10, 30)
INICIO_CANCELAMENTO = date(2026, 11, 3)
FIM_CANCELAMENTO = date(2026, 12, 20)
BASE_LEGAL = "LC 214/2025, art. 41; LC 123/2006, art. 13, §§ 9º a 11 (LC 227/2026); Res. CGSN 194/2026"
_LIMITE_SIMPLES = Decimal("4800000")


def _atividade(cliente: Cliente, perfil: PerfilEmpresa | None) -> Atividade | None:
    if perfil is not None:
        return perfil.atividade
    try:
        return Atividade(cliente.atividade) if cliente.atividade else None
    except ValueError:
        return None


def _texto_equilibrio(entrada: reforma_simples.EntradaSimplesReforma, cenario: reforma_simples.CenarioAno) -> str:
    if cenario.equilibrio_b2b is not None:
        return f"a partir de {float(cenario.equilibrio_b2b) * 100:.0f}% de vendas a empresas (B2B)"
    curva = reforma_simples.curva_b2b(entrada, cenario.ano, pontos=2)
    return "com qualquer porcentagem de vendas B2B" if curva[0][1] > 0 else "nem vendendo só a empresas (B2B)"


def aviso_regime_regular(
    cliente: Cliente, perfil: PerfilEmpresa | None, rbt12: Decimal | None, fonte: str, hoje: date
) -> tuple[avisos.Aviso, dict[str, Any]] | None:
    """Aviso do prazo da opção (até 30/10/2026) e a ação para simular o Simples na Reforma; ``None`` depois do prazo."""
    if hoje > PRAZO_OPCAO:
        return None
    dias = (PRAZO_OPCAO - hoje).days
    quando = "hoje" if dias == 0 else "amanhã" if dias == 1 else f"em {dias} dias"
    gravidade = "critico" if dias <= 3 else "atencao"
    titulo = f"Regime regular de IBS/CBS em 2027: a opção vai até 30/10/2026 ({quando})"
    prazos = (
        "A opção para janeiro a junho de 2027 vai de 01/09 a 30/10/2026; quem optar pode cancelar, em caráter irretratável, de 03/11 a 20/12/2026 "
        "(Res. CGSN 194/2026). Quem vende só para consumidor final (B2C) costuma ficar no DAS."
    )
    atividade = _atividade(cliente, perfil)
    acao: dict[str, Any] = {"tipo": "reforma", "rotulo": "Simular o Simples na Reforma", "aba": "simples"}
    if atividade is None or rbt12 is None or rbt12 <= 0 or rbt12 > _LIMITE_SIMPLES:
        detalhe = "Informe a receita e a atividade do cliente (um planejamento salvo ou notas importadas) para comparar. " + prazos
        return avisos.Aviso("regime_regular_prazo", gravidade, titulo, detalhe, None, BASE_LEGAL), acao

    folha = simples.folha_fator_r(perfil) if perfil is not None and atividade is Atividade.SERVICO_FATOR_R else None
    entrada = reforma_simples.EntradaSimplesReforma(atividade, rbt12, "0.5", folha_fator_r_anual=folha, anos=[2027])
    cenario = reforma_simples.simular(entrada)[0]
    compensa = _texto_equilibrio(entrada, cenario)
    com_compras = ""
    if perfil is not None and perfil.compras_anual > 0:
        # limite superior: se todas as compras do planejamento forem de fornecedores do regime regular (geram crédito integral por fora)
        entrada_c = reforma_simples.EntradaSimplesReforma(
            atividade, rbt12, "0.5", compras_creditaveis_anual=perfil.compras_anual, folha_fator_r_anual=folha, anos=[2027]
        )
        com_compras = (
            f" Com as compras de {brl(perfil.compras_anual)} do planejamento, se todas forem de fornecedores do regime regular, "
            f"compensa {_texto_equilibrio(entrada_c, reforma_simples.simular(entrada_c)[0])}."
        )
    detalhe = (
        f"Com receita de {brl(rbt12)} ({fonte}), recolher IBS/CBS por fora em 2027 compensa {compensa}, sem contar compras de fornecedores "
        f"do regime regular (que aumentam a vantagem).{com_compras} Confira a proporção de vendas a empresas do cliente. {prazos}"
    ).replace("compensa nem vendendo", "não compensa nem vendendo")
    acao.update({"receita": float(rbt12), "atividade": atividade.value})
    return avisos.Aviso("regime_regular_prazo", gravidade, titulo, detalhe, None, BASE_LEGAL), acao
