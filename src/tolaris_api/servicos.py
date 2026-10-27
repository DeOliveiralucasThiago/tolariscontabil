"""Ponte entre a API e o motor: executa simulações e serializa os resultados."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

import tolaris_motor
from tolaris_motor import Comparativo, PerfilEmpresa, Resultado, comparar, simulacao_expressa
from tolaris_motor import autonomo, enquadramento, pessoa_fisica, reforma, reforma_simples, simples

from tolaris_motor.empresa import Atividade

from .schemas import (
    AutonomoEntrada,
    CompletaEntrada,
    EnquadramentoEntrada,
    ExpressaEntrada,
    ProLaboreEntrada,
    ReformaEntrada,
    SalarioEntrada,
    SimplesReformaEntrada,
)

ROTULOS_ATIVIDADE = {
    "comercio": "Comércio",
    "industria": "Indústria",
    "servico_anexo_iii": "Serviços (Anexo III)",
    "servico_anexo_iv": "Serviços (Anexo IV)",
    "servico_fator_r": "Serviços sujeitos ao fator R",
}


def _num(v: Decimal, casas: int = 2) -> float:
    return float(round(v, casas))


def serializar_resultado(r: Resultado, receita: Decimal) -> dict[str, Any]:
    return {
        "titulo": r.titulo,
        "aplicavel": r.aplicavel,
        "total": _num(r.total),
        "carga_efetiva": _num(r.total / receita, 6) if receita and r.aplicavel else None,
        "tributos": [{"nome": n, "valor": _num(v)} for n, v in r.tributos.items()],
        "memoria": [
            {"descricao": p.descricao, "formula": p.formula, "valor": _num(p.valor, 6), "base_legal": p.base_legal}
            for p in r.memoria
        ],
        "alertas": list(r.alertas),
    }


def serializar_comparativo(c: Comparativo) -> dict[str, Any]:
    receita = c.perfil.receita_bruta_anual
    return {
        "receita_anual": _num(receita),
        "receita_exterior_anual": _num(c.perfil.receita_exterior_anual),
        "variacao_cambial_anual": _num(c.perfil.variacao_cambial_anual),
        "atividade": c.perfil.atividade.value,
        "ano": c.perfil.ano,
        "regimes": [serializar_resultado(r, receita) for r in c.resultados],
        "melhor": c.melhor.titulo,
        "ranking": [r.titulo for r in c.aplicaveis],
        "economia_vs_segundo": _num(c.economia_vs_segundo),
        "economia_vs_pior": _num(c.economia_vs_pior),
        "alertas": list(c.alertas),
    }


def executar_expressa(e: ExpressaEntrada) -> dict[str, Any]:
    c = simulacao_expressa(
        faturamento_mensal=e.faturamento_mensal,
        folha_mensal=e.folha_mensal,
        atividade=e.atividade,
        pro_labore_mensal=e.pro_labore_mensal,
        margem_lucro=e.margem_lucro,
        ano=e.ano,
        receita_exterior_mensal=e.receita_exterior_mensal,
        reducao_ibs_cbs=e.reducao_ibs_cbs,
        natureza_juridica=e.natureza_juridica,
    )
    return serializar_comparativo(c)


def _receitas_por_anexo(perfil: PerfilEmpresa) -> list[tuple[str, Decimal]]:
    """Receita de cada Anexo do Simples, na ordem do cálculo (a atividade principal primeiro)."""
    return simples._partes_por_anexo(perfil)


def executar_enquadramento(e: EnquadramentoEntrada) -> dict[str, Any]:
    dados = e.model_dump(exclude={"percentual_anexo_iii", "receita_anexo_iii_anual"})
    perfil = PerfilEmpresa(**dados)
    cenarios = enquadramento.analisar(perfil, e.percentual_anexo_iii)
    atual = cenarios[0]
    melhor = enquadramento.recomendado(cenarios)
    receita = perfil.receita_bruta_anual
    folha = simples.folha_fator_r(perfil)
    saida = []
    for c in cenarios:
        simples_res = next(r for r in c.comparativo.resultados if r.titulo.startswith("Simples"))
        saida.append(
            {
                "chave": c.chave,
                "descricao": c.descricao,
                "observacao": c.observacao,
                "anexos_simples": c.anexos_simples,
                "simples": {"aplicavel": simples_res.aplicavel, "total": _num(simples_res.total) if simples_res.aplicavel else None},
                "regimes": [{"titulo": r.titulo, "aplicavel": r.aplicavel, "total": _num(r.total)} for r in c.comparativo.resultados],
                "melhor_regime": c.comparativo.melhor.titulo,
                "total_melhor": _num(c.comparativo.melhor.total),
                "custo_extra_anual": _num(c.custo_extra_anual),
                "total_com_custo_extra": _num(c.melhor_total),
                "economia_vs_atual": _num(atual.melhor_total - c.melhor_total),
                "alertas": [a for a in simples_res.alertas if "Receita segregada por atividade" not in a],
                "pro_labore_anual": _num(c.perfil.pro_labore_anual),
                "receita_anexo_iii": _num(
                    c.perfil.receita_anexo_iii_anual + c.perfil.receitas_outras_atividades.get(Atividade.SERVICO_ANEXO_III, Decimal(0))
                ),
                "receitas_por_anexo": [{"anexo": a, "receita": _num(v)} for a, v in _receitas_por_anexo(c.perfil)],
            }
        )
    economia = atual.melhor_total - melhor.melhor_total
    alertas = [
        "Os dois caminhos só valem na vida real: o pró-labore precisa ser pago de verdade, e a atividade do Anexo III precisa "
        "ser exercida de fato, com o CNAE no cadastro e nota fiscal do serviço, e a receita de cada atividade é segregada "
        "(LC 123/2006, art. 18, §§ 4º, 5º-B e 5º-F). A Receita enquadra pela atividade realmente exercida; incluir um CNAE sem a "
        "atividade pode ser desconsiderado, com cobrança, multa e até exclusão do Simples (art. 29, §§ 1º e 2º: impedimento de 3 "
        "anos, ou de 10 em caso de artifício ou fraude). Valide com o contador.",
        "Antes de comparar regimes, confirme que o Simples é permitido: não pode optar quem tem sócio domiciliado no exterior ou "
        "filial no exterior (LC 123/2006, art. 17, II; art. 3º, § 4º, XII), quem tem sócio administrador de outra empresa com receita "
        "global acima do limite (art. 3º, § 4º, V) ou sócios com relação de pessoalidade, subordinação e habitualidade com o contratante "
        "do serviço (art. 3º, § 4º, XI), nem quem tem débitos com o INSS ou as Fazendas sem exigibilidade suspensa (art. 17, V).",
    ]
    if not any(a is Atividade.SERVICO_FATOR_R for a, _ in perfil.partes_atividade):
        alertas.append(
            "Os caminhos de enquadramento são para empresas com serviços do fator R (Anexo III ou V conforme a folha: LC 123/2006, art. 18, "
            "§§ 5º-I, 5º-J e 5º-M). Para as demais atividades o Anexo já é definido pela atividade; veja a receita de cada Anexo no cenário atual."
        )
    return {
        "receita_anual": _num(receita),
        "atividade": perfil.atividade.value,
        "ano": perfil.ano,
        "fator_r_atual": _num(simples.fator_r(folha, receita), 6),
        "cenarios": saida,
        "recomendado": melhor.chave,
        "melhor": melhor.descricao,
        "economia_vs_pior": _num(max(Decimal(0), economia)),
        "alertas": alertas,
    }


def executar_completa(e: CompletaEntrada) -> dict[str, Any]:
    perfil = PerfilEmpresa(**e.model_dump())
    return serializar_comparativo(comparar(perfil))


def titulo_simulacao(tipo: str, resultado: dict[str, Any]) -> str:
    if tipo in TIPOS_FASE2:
        return f"{TIPOS_FASE2[tipo][2]} — {resultado['melhor']}"
    if tipo == "recuperacao":
        return f"Recuperação de tributos — {resultado['melhor']}"
    nome = "Simulação expressa" if tipo == "expressa" else "Planejamento tributário"
    return f"{nome} {resultado['ano']} — melhor: {resultado['melhor']}"


VERSAO_MOTOR = tolaris_motor.__version__


# --- Fase 2 ------------------------------------------------------------------------
DATA_BASE = date(2026, 1, 1)


def _resultado_simples(r: Resultado) -> dict[str, Any]:
    """Tributos, memória e alertas de um resultado (as demais chaves vêm explícitas de quem chama)."""
    d = serializar_resultado(r, Decimal(0))
    return {k: d[k] for k in ("tributos", "memoria", "alertas")}


def executar_reforma(e: ReformaEntrada) -> dict[str, Any]:
    entrada = reforma.EntradaReforma(**e.model_dump())
    anos = reforma.simular(entrada)
    primeiro, ultimo = anos[0], anos[-1]
    atuais = ("PIS/Cofins", "IPI", "ICMS", "ISS")
    return {
        "base_venda": _num(reforma.base_venda_sem_tributos(entrada)),
        "base_credito": _num(reforma.base_credito_sem_tributos(entrada)),
        "cbs_referencia": _num(entrada.cbs_referencia, 4),
        "ibs_referencia": _num(entrada.ibs_referencia, 4),
        "anos": [
            {
                "ano": a.ano,
                "total": _num(a.total),
                "carga": _num(a.carga_sobre_base, 6),
                "atuais": _num(sum((v for k, v in a.resultado.tributos.items() if k in atuais), Decimal(0))),
                "novos": _num(sum((v for k, v in a.resultado.tributos.items() if k in ("CBS", "IBS")), Decimal(0))),
                **_resultado_simples(a.resultado),
            }
            for a in anos
        ],
        "variacao_total": _num(ultimo.total - primeiro.total),
        "variacao_carga_pp": _num((ultimo.carga_sobre_base - primeiro.carga_sobre_base) * 100, 4),
        "melhor": f"Carga em {ultimo.ano}: {float(ultimo.carga_sobre_base) * 100:.2f}%".replace(".", ","),
        "economia_vs_pior": 0.0,
        "alertas": list(primeiro.resultado.alertas),
    }


def _texto_equilibrio(entrada: reforma_simples.EntradaSimplesReforma, c: reforma_simples.CenarioAno) -> str:
    if c.equilibrio_b2b is not None:
        return f"a partir de {float(c.equilibrio_b2b) * 100:.0f}% de vendas B2B"
    curva = reforma_simples.curva_b2b(entrada, c.ano, pontos=2)
    return "com qualquer % de vendas B2B" if curva[0][1] > 0 else "não compensa nem com 100% B2B"


def executar_simples_reforma(e: SimplesReformaEntrada) -> dict[str, Any]:
    entrada = reforma_simples.EntradaSimplesReforma(**e.model_dump())
    cenarios = reforma_simples.simular(entrada)
    final = cenarios[-1]
    return {
        "cenarios": [
            {
                "ano": c.ano,
                "dentro_do_das": _num(c.dentro_do_das),
                "por_fora": _num(c.por_fora),
                "diferenca": _num(c.diferenca),
                "equilibrio_b2b": _num(c.equilibrio_b2b, 4) if c.equilibrio_b2b is not None else None,
                "equilibrio_texto": _texto_equilibrio(entrada, c),
                "credito_cliente_dentro": _num(c.credito_cliente_dentro),
                "credito_cliente_fora": _num(c.credito_cliente_fora),
                "recomendacao": c.recomendacao,
                **_resultado_simples(c.resultado),
            }
            for c in cenarios
        ],
        "curvas": {
            str(c.ano): [
                {"b2b": _num(b, 2), "diferenca": _num(d)} for b, d in reforma_simples.curva_b2b(entrada, c.ano)
            ]
            for c in cenarios
        },
        "percentual_b2b": _num(entrada.percentual_b2b, 4),
        "melhor": final.recomendacao,
        "economia_vs_pior": _num(abs(final.diferenca)),
        "alertas": [],
    }


def executar_autonomo(e: AutonomoEntrada) -> dict[str, Any]:
    c = autonomo.comparar(autonomo.EntradaAutonomo(**e.model_dump(), data=DATA_BASE))
    return {
        "opcoes": [
            {
                "nome": o.nome,
                "aplicavel": o.aplicavel,
                "tributos_mensais": _num(o.tributos_mensais),
                "custos_mensais": _num(o.custos_mensais),
                "liquido_mensal": _num(o.liquido_mensal),
                "detalhe": o.detalhe,
                **_resultado_simples(o.resultado),
            }
            for o in c.opcoes
        ],
        "receita_mensal": _num(c.entrada.receita_mensal),
        "melhor": c.melhor.nome,
        "ranking": [o.nome for o in c.aplicaveis],
        "ganho_vs_autonomo_anual": _num(c.ganho_vs_autonomo_anual),
        "economia_vs_pior": _num(max(Decimal(0), c.ganho_vs_autonomo_anual)),
        "alertas": list(c.alertas),
    }


def executar_pro_labore(e: ProLaboreEntrada) -> dict[str, Any]:
    a, b = pessoa_fisica.comparar_pro_labore_dividendos(
        e.retirada_mensal, DATA_BASE, regime=e.regime, pro_labore_otimizado=e.pro_labore_otimizado
    )
    economia = a.custo_mensal - b.custo_mensal
    return {
        "cenarios": [
            {
                "descricao": c.descricao,
                "pro_labore": _num(c.pro_labore),
                "dividendos": _num(c.dividendos),
                "custo_mensal": _num(c.custo_mensal),
                "liquido_mensal": _num(c.pro_labore + c.dividendos - sum(
                    (v for k, v in c.resultado.tributos.items() if k.startswith(("INSS do sócio", "IRPF", "IRRF"))),
                    Decimal(0),
                )),
                **_resultado_simples(c.resultado),
            }
            for c in (a, b)
        ],
        "regime": e.regime,
        "economia_mensal": _num(economia),
        "economia_anual": _num(economia * 12),
        "melhor": b.descricao if economia > 0 else a.descricao,
        "economia_vs_pior": _num(abs(economia) * 12),
        "alertas": [],
    }


def executar_salario(e: SalarioEntrada) -> dict[str, Any]:
    r = pessoa_fisica.salario_liquido(e.salario_bruto, DATA_BASE, e.dependentes, e.pensao_alimenticia)
    return {"salario_bruto": _num(e.salario_bruto), "liquido": _num(r.memoria[-1].valor), **_resultado_simples(r)}


# Tipos de simulação que podem ser salvos no cliente: entrada, executor e nome para o título
TIPOS_FASE2: dict[str, tuple[type, Any, str]] = {
    "reforma": (ReformaEntrada, executar_reforma, "Reforma Tributária 2025–2033"),
    "simples_reforma": (SimplesReformaEntrada, executar_simples_reforma, "Simples na Reforma (IBS/CBS no DAS ou por fora)"),
    "autonomo": (AutonomoEntrada, executar_autonomo, "Autônomo × CNPJ"),
    "pro_labore": (ProLaboreEntrada, executar_pro_labore, "Pró-labore × dividendos"),
    "enquadramento": (EnquadramentoEntrada, executar_enquadramento, "Enquadramento: caminhos para o Anexo III"),
}


# --- Recálculo de simulações salvas -------------------------------------------------------
def _executor_do_tipo(tipo: str) -> tuple[type, Any] | None:
    base = {"expressa": (ExpressaEntrada, executar_expressa), "completa": (CompletaEntrada, executar_completa)}
    if tipo in base:
        return base[tipo]
    if tipo in TIPOS_FASE2:
        modelo, executor, _ = TIPOS_FASE2[tipo]
        return modelo, executor
    return None


def pode_recalcular(tipo: str) -> bool:
    return _executor_do_tipo(tipo) is not None


def recalcular_resultado(tipo: str, entrada: dict[str, Any]) -> dict[str, Any]:
    """Executa de novo, com as regras atuais, uma simulação salva (só os tipos que dependem apenas da entrada)."""
    modelo, executor = _executor_do_tipo(tipo)  # type: ignore[misc]
    return executor(modelo(**entrada))


_IGNORAR = {"alertas", "memoria", "recalculo", "formula", "base_legal", "descricao", "detalhe", "equilibrio_texto", "recomendacao"}


def _achatar(valor: Any, caminho: str = "") -> dict[str, Any]:
    """Números (e o campo ``melhor``) de um resultado, por caminho, sem os textos explicativos."""
    if isinstance(valor, dict):
        saida: dict[str, Any] = {}
        for k, v in valor.items():
            if k in _IGNORAR:
                continue
            saida.update(_achatar(v, f"{caminho}.{k}" if caminho else k))
        return saida
    if isinstance(valor, list):
        saida = {}
        for i, v in enumerate(valor):
            saida.update(_achatar(v, f"{caminho}[{i}]"))
        return saida
    if isinstance(valor, bool) or valor is None:
        return {}
    if isinstance(valor, (int, float)):
        return {caminho: float(valor)}
    if isinstance(valor, str) and caminho.split(".")[-1] == "melhor":
        return {caminho: valor}
    return {}


def diferencas(antigo: dict[str, Any], novo: dict[str, Any]) -> list[str]:
    """Caminhos cujo valor mudou (mais de 1 centavo). Campos que existem só de um lado são ignorados:
    mudar o formato do resultado não deve parecer mudança de regra."""
    a, b = _achatar(antigo), _achatar(novo)
    mudou = []
    for caminho in a.keys() & b.keys():
        x, y = a[caminho], b[caminho]
        if isinstance(x, float) and isinstance(y, float):
            if abs(x - y) > 0.011:
                mudou.append(caminho)
        elif x != y:
            mudou.append(caminho)
    return sorted(mudou)
