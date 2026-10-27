"""Simples Nacional: alíquota efetiva por anexo/faixa, fator R e DAS anual estimado."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from . import natureza_juridica, tabelas
from .base import ZERO, D, Numero, Resultado, brl, pct
from .empresa import ALIQUOTA_CPP, Atividade, PerfilEmpresa

BASE_LEGAL_ALIQUOTA = "LC 123/2006, art. 18, §1º e §1º-A"
BASE_LEGAL_FATOR_R = "LC 123/2006, art. 18, §5º-J, §5º-M e §24"


def _tabela(data: date) -> dict:
    return tabelas.vigente("simples_nacional", data)


def faixa(anexo: str, rbt12: Numero, data: date | None = None, extrapolar: bool = False) -> tuple[int, dict]:
    """Retorna (número da faixa 1..6, dados da faixa) para a receita bruta dos últimos 12 meses.

    ``extrapolar`` usa a última faixa quando o RBT12 passa do teto (só acontece com receita de exportação,
    que tem limite próprio além dos R$ 4,8 mi do mercado interno).
    """
    rbt12 = D(rbt12)
    tab = _tabela(data or date.today())
    faixas = tab["anexos"][anexo]["faixas"]
    for i, f in enumerate(faixas, start=1):
        if rbt12 <= D(f["ate"]):
            return i, f
    if extrapolar:
        return len(faixas), faixas[-1]
    raise ValueError(f"RBT12 de {brl(rbt12)} excede o limite do Simples Nacional")


def aliquota_efetiva(anexo: str, rbt12: Numero, data: date | None = None, extrapolar: bool = False) -> Decimal:
    """(RBT12 x alíquota nominal - parcela a deduzir) / RBT12.

    Para RBT12 zero (empresa em início de atividade) aplica-se a alíquota nominal da 1ª faixa.
    """
    rbt12 = D(rbt12)
    _, f = faixa(anexo, rbt12, data, extrapolar)
    if rbt12 == 0:
        return D(f["aliquota"])
    return (rbt12 * D(f["aliquota"]) - D(f["deduzir"])) / rbt12


def folha_fator_r(perfil: PerfilEmpresa) -> Decimal:
    """Folha de salários para o fator R: salários + pró-labore + FGTS (salvo valor informado)."""
    if perfil.folha_fator_r_anual is not None:
        return perfil.folha_fator_r_anual
    return perfil.folha_clt_anual + perfil.pro_labore_anual + perfil.fgts_anual


def fator_r(folha_12m: Numero, rbt12: Numero) -> Decimal:
    rbt12 = D(rbt12)
    return D(folha_12m) / rbt12 if rbt12 > 0 else ZERO


def pro_labore_minimo_fator_r(
    rbt12: Numero, folha_atual_12m: Numero, data: date | None = None
) -> Decimal:
    """Pró-labore MENSAL adicional necessário para o fator R atingir 28% (Anexo III em vez do V)."""
    minimo = D(_tabela(data or date.today())["fator_r_minimo"])
    falta = D(rbt12) * minimo - D(folha_atual_12m)
    return max(ZERO, falta) / 12


AJUSTE_ANEXO: dict[Atividade, tuple[str, str]] = {
    Atividade.LOCACAO_BENS_MOVEIS: ("III", "sem_iss"),
    Atividade.INDUSTRIA_IPI_ISS: ("II", "icms_por_iss"),
    Atividade.TRANSPORTE_CARGAS_ICMS: ("III", "iss_por_icms"),
    Atividade.TRANSPORTE_PASSAGEIROS_ICMS: ("III", "iss_por_icms"),
    Atividade.COMUNICACAO_ICMS: ("III", "iss_por_icms"),
}
"""Anexo e ajuste da partilha de cada atividade do art. 25, § 1º, VI, VII e IX, da Res. CGSN 140/2018 (LC 123/2006, art. 18, §§ 4º, V e VI, e 5º-E)."""
ROTULO_AJUSTE = {
    "": "",
    "sem_iss": " sem a parcela do ISS",
    "icms_por_iss": " sem a parcela do ICMS e com a do ISS do Anexo III",
    "iss_por_icms": " sem a parcela do ISS e com a do ICMS do Anexo I",
}
BASE_LEGAL_AJUSTE = {
    "sem_iss": "LC 123/2006, art. 18, § 4º, V; Res. CGSN 140/2018, art. 25, § 1º, VI",
    "icms_por_iss": "LC 123/2006, art. 18, § 4º, VI; Res. CGSN 140/2018, art. 25, § 1º, VII",
    "iss_por_icms": "LC 123/2006, art. 18, § 5º-E; Res. CGSN 140/2018, art. 25, § 1º, IX",
}


def anexo_da_atividade(perfil: PerfilEmpresa, res: Resultado | None = None, atividade: Atividade | None = None) -> str:
    """Anexo do Simples da atividade (a principal, se não vier outra). O fator R usa a receita e a folha totais da empresa."""
    a = atividade or perfil.atividade
    if a is Atividade.COMERCIO:
        return "I"
    if a is Atividade.INDUSTRIA:
        return "II"
    if a is Atividade.SERVICO_ANEXO_III:
        return "III"
    if a is Atividade.SERVICO_ANEXO_IV:
        return "IV"
    if a in AJUSTE_ANEXO:
        return AJUSTE_ANEXO[a][0]
    data = date(perfil.ano, 1, 1)
    minimo = D(_tabela(data)["fator_r_minimo"])
    folha = folha_fator_r(perfil)
    r = fator_r(folha, perfil.receita_bruta_anual)
    anexo = "III" if r >= minimo else "V"
    if res is not None:
        origem = "informada" if perfil.folha_fator_r_anual is not None else "salários + pró-labore + FGTS 8%"
        res.passo(
            "Fator R (folha 12 meses / RBT12)",
            f"{brl(folha)} ({origem}) / {brl(perfil.receita_bruta_anual)} = {pct(r)} "
            f"-> Anexo {anexo}",
            r,
            BASE_LEGAL_FATOR_R,
        )
        if perfil.folha_fator_r_anual is None:
            res.alerta(
                "Folha do fator R (LC 123/2006, art. 18, §§ 24 a 26; Res. CGSN 140/2018, art. 26): remunerações pagas a pessoas "
                "físicas (com o 13º salário), pró-labore e FGTS; não entram aluguéis nem distribuição de lucros. A contribuição "
                "patronal só entra se for recolhida fora do DAS, o que não é o caso dos Anexos III e V. Se o valor apurado no "
                "eSocial ou no PGDAS-D for diferente, informe-o em \"Folha do fator R informada\"."
            )
        if anexo == "V":
            extra = pro_labore_minimo_fator_r(perfil.receita_bruta_anual, folha, data)
            res.alerta(
                f"Fator R abaixo de {pct(minimo, 0)}: acrescentar cerca de {brl(extra)}/mês de "
                "pró-labore levaria ao Anexo III. Compare o custo do INSS sobre esse pró-labore."
            )
    return anexo


def _partes_simples(perfil: PerfilEmpresa, res: Resultado | None = None) -> list[tuple[str, str, Decimal]]:
    """Receita por (Anexo, ajuste da partilha): cada atividade no seu Anexo (LC 123/2006, art. 18, § 4º); o que cai no mesmo par soma."""
    por_parte: dict[tuple[str, str], Decimal] = {}
    fator_r_lancado = False
    for atividade, valor in perfil.partes_atividade:
        lancar = res if atividade is Atividade.SERVICO_FATOR_R and not fator_r_lancado else None
        fator_r_lancado = fator_r_lancado or atividade is Atividade.SERVICO_FATOR_R
        anexo = anexo_da_atividade(perfil, lancar, atividade)
        chave = (anexo, AJUSTE_ANEXO[atividade][1] if atividade in AJUSTE_ANEXO else "")
        por_parte[chave] = por_parte.get(chave, ZERO) + valor
    return [(anexo, ajuste, valor) for (anexo, ajuste), valor in por_parte.items()]


def _partes_por_anexo(perfil: PerfilEmpresa, res: Resultado | None = None) -> list[tuple[str, Decimal]]:
    """Receita por Anexo (sem separar os ajustes da partilha)."""
    por_anexo: dict[str, Decimal] = {}
    for anexo, _, valor in _partes_simples(perfil, res):
        por_anexo[anexo] = por_anexo.get(anexo, ZERO) + valor
    return list(por_anexo.items())


def aliquota_da_parte(anexo: str, ajuste: str, rbt12: Numero, data: date) -> tuple[Decimal, str]:
    """Alíquota efetiva aplicada à parte da receita e a fórmula do ajuste (vazia quando não há).

    Os percentuais efetivos de cada tributo são a alíquota efetiva x a repartição da faixa (LC 123/2006, art. 18, § 1º-B)."""
    aliq = aliquota_efetiva(anexo, rbt12, data)
    if not ajuste:
        return aliq, ""
    if ajuste == "sem_iss":
        iss = partilha("III", rbt12, data).get("iss", ZERO)
        return aliq * (1 - iss), f"{pct(aliq, 4)} x (1 - {pct(iss, 2)} de ISS do Anexo III)"
    if ajuste == "iss_por_icms":
        iss = partilha("III", rbt12, data).get("iss", ZERO)
        aliq_i, icms = aliquota_efetiva("I", rbt12, data), partilha("I", rbt12, data).get("icms", ZERO)
        return (
            aliq * (1 - iss) + aliq_i * icms,
            f"{pct(aliq, 4)} x (1 - {pct(iss, 2)} de ISS do Anexo III) + {pct(aliq_i, 4)} do Anexo I x {pct(icms, 2)} de ICMS",
        )
    # icms_por_iss: Anexo II sem o ICMS e com o ISS do Anexo III
    icms = partilha("II", rbt12, data).get("icms", ZERO)
    aliq_iii, iss = aliquota_efetiva("III", rbt12, data), partilha("III", rbt12, data).get("iss", ZERO)
    return (
        aliq * (1 - icms) + aliq_iii * iss,
        f"{pct(aliq, 4)} x (1 - {pct(icms, 2)} de ICMS do Anexo II) + {pct(aliq_iii, 4)} do Anexo III x {pct(iss, 2)} de ISS",
    )


BASE_LEGAL_ISS_FIXO = "LC 123/2006, art. 18, § 5º-B, XIV e § 22-A; Res. CGSN 140/2018, art. 25, § 1º, VIII, e art. 34"
BASE_LEGAL_EXPORTACAO = "Res. CGSN 140/2018, art. 25, §§ 3º, 4º e 4º-A; LC 116/2003, art. 2º, I; LC 123/2006, art. 18"
TRIBUTOS_DESCONSIDERADOS_EXPORTACAO = {
    "servicos": ("pis", "cofins", "iss"),
    "mercadorias": ("pis", "cofins", "icms", "ipi"),
}
TRIBUTOS_DESCONSIDERADOS_EXPORTACAO_2027 = {
    "servicos": ("cbs", "ibs", "iss"),
    "mercadorias": ("cbs", "ibs", "icms", "ipi"),
}
"""A partir de 2027 as tabelas trazem CBS e IBS no lugar de PIS e Cofins (LC 123/2006, art. 18, §§ 14 e 14-A, redação da LC 214/2025)."""
INICIO_CBS_IBS = date(2027, 1, 1)


def tem_cbs_ibs(data: date) -> bool:
    """Se a tabela do Simples vigente na data já traz CBS e IBS na partilha (Res. CGSN 190/2026)."""
    return data >= INICIO_CBS_IBS


def tributos_desconsiderados_exportacao(tipo: str, data: date) -> tuple[str, ...]:
    tabela = TRIBUTOS_DESCONSIDERADOS_EXPORTACAO_2027 if tem_cbs_ibs(data) else TRIBUTOS_DESCONSIDERADOS_EXPORTACAO
    return tabela[tipo]


def alerta_exportacao(perfil: PerfilEmpresa, res: Resultado) -> None:
    """Avisos que acompanham qualquer cálculo com receita do exterior (iguais nos três regimes)."""
    consumo = "CBS e IBS" if perfil.ano >= 2027 else "PIS/Cofins"
    if perfil.receita_exterior_anual:
        if perfil.receita_mercadorias_anual > 0:
            res.alerta(
                f"Receita de exportação de mercadorias ({brl(perfil.receita_exterior_anual)}): tratada sem ICMS, IPI e "
                f"{consumo}. Guarde a declaração de exportação (DU-E) e o contrato de câmbio."
            )
        if perfil.receita_servicos_anual > 0:
            res.alerta(
                f"Receita de exportação de serviços ({brl(perfil.receita_exterior_anual)}): tratada sem ISS e sem "
                f"{consumo}. Só vale se o serviço foi prestado a residente no exterior, o resultado se verifica no "
                "exterior e o pagamento representa ingresso de divisas (Res. CGSN 140/2018, art. 25, §4º; "
                "LC 116/2003, art. 2º, parágrafo único). Guarde contrato, nota fiscal e contrato de câmbio."
            )
        if perfil.tem_atividades_mistas:
            res.alerta("Atividades mistas com exportação: a receita do exterior foi repartida entre as atividades na proporção da receita de cada uma.")
    if perfil.variacao_cambial_anual:
        res.alerta(
            f"Variação cambial líquida de {brl(perfil.variacao_cambial_anual)} informada: o tratamento depende do regime "
            "(veja os alertas de cada um)."
        )


def calcular(perfil: PerfilEmpresa) -> Resultado:
    """DAS anual estimado supondo faturamento mensal constante (RBT12 = receita anual)."""
    res = Resultado("Simples Nacional")
    data = date(perfil.ano, 1, 1)
    tab = _tabela(data)
    receita = perfil.receita_bruta_anual
    exterior = perfil.receita_exterior_anual
    interna = perfil.receita_interna_anual
    limite = D(tab["limite_receita_anual"])

    natureza = perfil.natureza
    if natureza_juridica.impede_simples(natureza):
        res.aplicavel = False
        res.alerta(f"Natureza jurídica \"{natureza.rotulo}\": {natureza.explicacao} ({natureza_juridica.BASE_LEGAL_ELEGIBILIDADE}).")
        return res

    if perfil.impedimentos_simples:
        res.aplicavel = False
        for texto in perfil.impedimentos_simples:
            res.alerta(f"Impedimento ao Simples Nacional confirmado no cadastro: {texto}.")
        return res

    # Mercado interno e exportação têm, cada um, o limite de R$ 4,8 mi (Res. CGSN 140/2018, art. 2º, §1º)
    if interna > limite or exterior > limite:
        res.aplicavel = False
        if exterior == 0:
            res.alerta(f"Receita acima de {brl(limite)}: empresa não pode optar pelo Simples Nacional.")
        elif interna > limite:
            res.alerta(f"Receita do mercado interno acima de {brl(limite)}: empresa não pode optar pelo Simples Nacional.")
        else:
            res.alerta(f"Receita de exportação acima de {brl(limite)}: empresa não pode optar pelo Simples Nacional.")
        return res

    partes = _partes_simples(perfil, res)
    multiplas = len(partes) > 1
    # A alíquota de cada mercado sai do RBT12 daquele mercado (LC 123/2006, art. 3º, § 15; Res. CGSN 140/2018, art. 23)
    mercados = [("mercado interno", interna), ("exportação", exterior)] if exterior else [("", receita)]
    das_total = ZERO
    passos_das: list[Decimal] = []
    for mercado, rbt12 in mercados:
        if rbt12 <= 0:
            continue
        em_mercado = f", {mercado}" if mercado else ""
        for anx, ajuste, parte in partes:
            n, f = faixa(anx, rbt12, data)
            aliq_efetiva = aliquota_efetiva(anx, rbt12, data)
            res.passo(
                f"Alíquota efetiva - Anexo {anx}, {n}ª faixa{em_mercado}",
                f"({brl(rbt12)} x {pct(D(f['aliquota']))} - {brl(f['deduzir'])}) / {brl(rbt12)} = {pct(aliq_efetiva, 4)}",
                aliq_efetiva,
                BASE_LEGAL_ALIQUOTA + ("; art. 3º, § 15" if mercado else ""),
            )
            aliq, formula_ajuste = aliquota_da_parte(anx, ajuste, rbt12, data)
            if ajuste:
                res.passo(
                    f"Alíquota aplicada - Anexo {anx}{ROTULO_AJUSTE[ajuste]}{em_mercado}", formula_ajuste + f" = {pct(aliq, 4)}", aliq, BASE_LEGAL_AJUSTE[ajuste]
                )
            valor = rbt12 * (parte / receita if receita else D(1))  # parcela do mercado neste Anexo
            desconsiderados = tributos_desconsiderados_exportacao("mercadorias" if anx in ("I", "II") else "servicos", data)
            sufixo = f" (Anexo {anx}{ROTULO_AJUSTE[ajuste]}, {brl(valor)})" if multiplas else ""
            tira_iss = perfil.iss_fixo_no_simples and anx == "III" and not ajuste and mercado != "exportação"
            fracao_iss = partilha(anx, rbt12, data).get("iss", ZERO) if tira_iss else ZERO
            if tira_iss:
                formula_iss = f" x (1 - {pct(fracao_iss, 2)} de ISS da partilha da faixa)"
                base_iss = BASE_LEGAL_ISS_FIXO
            else:
                formula_iss, base_iss = "", "LC 123/2006, art. 13"
            if not mercado:
                das_parte = res.passo(
                    "DAS anual" if not multiplas else f"DAS{sufixo}",
                    f"{brl(valor)} x {pct(aliq, 4)}{formula_iss}",
                    valor * aliq * (1 - fracao_iss),
                    base_iss,
                )
            elif mercado == "mercado interno":
                das_parte = res.passo(
                    f"DAS - mercado interno{sufixo}", f"{brl(valor)} x {pct(aliq, 4)}{formula_iss}",
                    valor * aliq * (1 - fracao_iss), base_iss if tira_iss else "LC 123/2006, art. 13",
                )
            else:
                fracoes = partilha(anx, rbt12, data)
                fracao_excluida = sum((fracoes.get(k, ZERO) for k in desconsiderados), ZERO)
                das_parte = res.passo(
                    f"DAS - exportação{sufixo}",
                    f"{brl(valor)} x {pct(aliq, 4)} x (1 - {pct(fracao_excluida, 2)} de "
                    f"{'/'.join(t.upper() for t in desconsiderados)} na partilha da faixa)",
                    valor * aliq * (1 - fracao_excluida),
                    BASE_LEGAL_EXPORTACAO,
                )
            das_total += das_parte
            passos_das.append(das_parte)
    if exterior == 0 and not multiplas:
        res.tributos["DAS"] = das_total
    else:
        res.tributos["DAS"] = res.passo(
            "DAS anual", " + ".join(brl(v) for v in passos_das), das_total, "LC 123/2006, art. 13 e art. 18, §§ 1º e 4º"
        )
    if multiplas:
        anexos_txt = ", ".join(f"Anexo {anx}{ROTULO_AJUSTE[ajuste]} ({brl(v)})" for anx, ajuste, v in partes)
        res.alerta(
            f"Receita segregada por atividade: {anexos_txt}. Cada atividade tributa no Anexo da atividade realmente exercida, com a faixa "
            "pela receita total. Só vale se a empresa exerce de fato cada atividade, tem o CNAE no cadastro e emite a nota com a atividade "
            "correspondente, separando as receitas no PGDAS-D (LC 123/2006, art. 18, §§ 4º e 5º-B). Não basta incluir o CNAE: a Receita "
            "enquadra pela atividade realmente exercida."
        )

    if any(ajuste for _, ajuste, _ in partes):
        res.alerta(
            "Atividade com partilha ajustada (locação de bens móveis, IPI com ISS, transporte intermunicipal ou comunicação): o DAS usa a alíquota efetiva do Anexo, "
            "tira a parcela do ISS ou do ICMS que não é devida e põe a do outro tributo (Res. CGSN 140/2018, art. 25, § 1º, VI, VII e IX). O Tolaris aplica o "
            "percentual efetivo de cada tributo (alíquota efetiva x repartição da faixa, LC 123/2006, art. 18, § 1º-B); o texto da resolução não traz a conta passo a "
            "passo, então confira o valor no PGDAS-D."
        )
    if perfil.iss_fixo_no_simples:
        res.tributos["ISS fixo (recolhido ao Município, fora do DAS)"] = res.passo(
            "ISS fixo do escritório de serviços contábeis",
            f"{perfil.profissionais} profissional(is) x {brl(perfil.iss_fixo_por_profissional_anual)}/ano",
            perfil.iss_fixo_anual,
            BASE_LEGAL_ISS_FIXO,
        )
        res.alerta(
            "ISS fixo do escritório de serviços contábeis: o DAS não inclui o ISS e o imposto é pago em valor fixo diretamente ao Município, "
            "conforme a lei municipal (Res. CGSN 140/2018, art. 34). Se o Município não autorizar esse recolhimento, o ISS vai no DAS pela receita "
            "(art. 25, § 11): desmarque a opção. Informe o ISS fixo no PGDAS-D e confirme o valor e as condições com a prefeitura."
        )
    receita_iv = sum((v for anx, _, v in partes if anx == "IV"), ZERO)
    if receita_iv > 0:
        aliq_folha = ALIQUOTA_CPP + perfil.rat
        parte_iv = receita_iv / receita if receita else D(1)
        cpp_cheia = perfil.folha_clt_anual * aliq_folha + perfil.pro_labore_anual * ALIQUOTA_CPP
        formula_cpp = (
            f"{brl(perfil.folha_clt_anual)} x ({pct(ALIQUOTA_CPP)} + {pct(perfil.rat)} RAT) + "
            f"{brl(perfil.pro_labore_anual)} x {pct(ALIQUOTA_CPP)}"
        )
        fracao_cpp = D(1)
        if multiplas:
            # IN RFB 2.110/2022, arts. 168 a 171: empregados só do Anexo IV pagam a CPP integral; os que atuam nas duas atividades, na proporção
            # da receita do Anexo IV; os que atuam só nas outras já estão com a CPP dentro do DAS.
            so_iv, so_outros = perfil.folha_so_anexo_iv_pct, perfil.folha_so_outros_anexos_pct
            concomitante = 1 - so_iv - so_outros
            fracao_cpp = so_iv + concomitante * parte_iv
            formula_cpp = (
                f"({formula_cpp}) x ({pct(so_iv, 0)} da folha só do Anexo IV + {pct(concomitante, 0)} nas duas atividades x "
                f"{pct(parte_iv, 2)} da receita no Anexo IV) = x {pct(fracao_cpp, 2)}"
            )
        res.tributos["INSS patronal (fora do DAS)"] = res.passo(
            "CPP fora do DAS (Anexo IV)",
            formula_cpp,
            cpp_cheia * fracao_cpp,
            "LC 123/2006, art. 18, § 5º-C e art. 13, VI" + ("; Res. CGSN 140/2018, art. 147; IN RFB 2.110/2022, arts. 168 a 171" if multiplas else ""),
        )
        if multiplas:
            res.alerta(
                "Atividade do Anexo IV junto com outras: a CPP patronal sai do DAS só para a folha ligada ao Anexo IV (IN RFB 2.110/2022, arts. 168 a 171): "
                "empregados só do Anexo IV pagam a CPP inteira, os que atuam nas duas atividades pagam na proporção da receita do Anexo IV e os que atuam só nas "
                "outras já estão cobertos pelo DAS. "
                + (
                    "Foi usada a divisão da folha informada."
                    if perfil.folha_so_anexo_iv_pct or perfil.folha_so_outros_anexos_pct
                    else "Sem a divisão da folha por atividade, o Tolaris tratou todos os empregados como atuando nas duas atividades (CPP na proporção da receita do Anexo IV)."
                )
            )

    if interna > D(tab["sublimite_icms_iss"]):
        res.alerta(
            f"Receita acima do sublimite de {brl(tab['sublimite_icms_iss'])}: ICMS/ISS passam a ser "
            "recolhidos fora do DAS. Este cálculo usa a alíquota cheia do DAS (aproximação)."
        )
    alerta_exportacao(perfil, res)
    if perfil.variacao_cambial_anual:
        res.alerta(
            "Simples: a variação cambial não entra neste cálculo do DAS. Confirme com o contador se ela integra a "
            "receita bruta (depende de ser variação ligada a receita de exportação ou receita financeira)."
        )
    if tem_cbs_ibs(data):
        res.alerta(
            "Tabelas de 2027 em diante (Res. CGSN 190/2026): CBS e IBS ocupam, em cada faixa, a fatia que era de PIS, Cofins, ICMS e ISS "
            "(IPI da indústria permanece), em transição até 2033; o teto do ISS no DAS cai de 5% (2027-28) a 3% (2032). A RBT12 passa a "
            "contar os 12 meses anteriores ao mês anterior ao da apuração. A partir de 2027 a empresa pode recolher IBS e CBS pelo regime "
            "regular (veja o Simples na Reforma). Texto lido nos autógrafos das leis; confirme na versão publicada."
        )
    if exterior:
        if tem_cbs_ibs(data):
            res.alerta(
                "Exportação em 2027 em diante: a redução do DAS corresponde às alíquotas efetivas de ICMS, ISS, IPI, IBS e CBS (LC 123/2006, "
                "art. 18, §§ 14 e 14-A, redação da LC 214/2025); cada mercado usa o RBT12 do próprio mercado e os §§ 4º e 4º-A do art. 25 da "
                "Res. CGSN 140/2018 foram revogados (a qualificação como exportação segue as regras de cada tributo, § 4º-B). Confira a "
                "qualificação da operação antes de segregar a receita no PGDAS-D."
            )
        else:
            res.alerta(
                "Cálculo pelas regras vigentes em 2026 (LC 123/2006, art. 3º, § 15 e art. 18, § 14; Res. CGSN 140/2018, arts. 23 e 25): "
                "cada mercado usa o RBT12 do próprio mercado. A partir de 01/01/2027 (Res. CGSN 190/2026) a RBT12 passa a contar os 12 meses "
                "anteriores ao mês anterior ao da apuração, a separação entre os mercados continua, e os §§ 4º e 4º-A do art. 25 são "
                "revogados: a qualificação como exportação de serviços passa a seguir as regras de cada tributo (§ 4º-B). Confira a "
                "qualificação da operação como exportação antes de segregar a receita no PGDAS-D."
            )
        res.alerta(
            "Vedações a conferir para quem exporta (LC 123/2006, art. 17, II e art. 3º, § 4º, XII): titular ou sócio domiciliado no "
            "exterior, ou filial, sucursal, agência ou representação no exterior, impedem o Simples Nacional."
        )
    if perfil.sociedade_profissionais and not perfil.iss_fixo_no_simples:
        res.alerta(
            "Sociedade de profissionais com ISS fixo: no Simples Nacional o ISS é calculado sobre a receita e vai no DAS; o ISS fixo da "
            "sociedade uniprofissional não vale para o optante. A exceção legal é o escritório de serviços contábeis, que pode recolher o ISS fixo "
            "ao Município se a lei municipal permitir (LC 123/2006, art. 18, § 22-A): para esse caso (atividade do Anexo III), marque "
            "\"recolhe o ISS fixo também no Simples\"."
        )
    if perfil.servicos_hospitalares:
        res.alerta("A presunção de serviços hospitalares é do Lucro Presumido e não muda o cálculo do Simples Nacional.")
    res.alerta("Estimativa com faturamento mensal constante; o DAS real varia mês a mês com o RBT12.")
    return res


TRIBUTOS_FORA_DO_TETO_ISS = ("iss", "icms")
"""O excesso de ISS acima do teto vai, na proporção da faixa, para todos os demais tributos da partilha (federais, CBS e IBS)."""


def partilha(anexo: str, rbt12: Numero, data: date | None = None, extrapolar: bool = False) -> dict[str, Decimal]:
    """Fração do DAS que cabe a cada tributo na faixa do RBT12.

    Aplica o teto de ISS efetivo da tabela (5% até 2028 e, depois, 4,5%, 4%, 3,5% e 3%): o excesso vai, proporcionalmente,
    aos demais tributos da mesma faixa (LC 123/2006, Anexo III, nota da 5ª faixa).
    """
    data = data or date.today()
    _, f = faixa(anexo, rbt12, data, extrapolar)
    fracoes = {k: D(v) for k, v in f["partilha"].items()}
    teto_iss = D(_tabela(data)["iss_efetivo_maximo"])
    aliq = aliquota_efetiva(anexo, rbt12, data, extrapolar)
    iss = fracoes.get("iss", ZERO)
    if aliq > 0 and aliq * iss > teto_iss:
        nova = teto_iss / aliq
        excesso = iss - nova
        demais = {k: v for k, v in fracoes.items() if k not in TRIBUTOS_FORA_DO_TETO_ISS}
        soma = sum(demais.values(), ZERO)
        for k, v in demais.items():
            fracoes[k] = v + excesso * v / soma
        fracoes["iss"] = nova
    return fracoes
