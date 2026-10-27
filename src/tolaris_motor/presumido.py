"""Lucro Presumido: IRPJ/CSLL trimestrais, PIS/Cofins cumulativos, ISS/ICMS e INSS patronal."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from . import consumo, tabelas
from .base import ZERO, D, Resultado, brl, pct
from .empresa import PRESUNCAO_PADRAO, PerfilEmpresa, inss_patronal_regime_normal, tributo_sobre_receita_local
from .simples import alerta_exportacao


def _base_presumida(
    res: Resultado,
    tributo: str,
    receita_trim: Decimal,
    percentual: Decimal,
    lc224: dict | None,
    inicio_acrescimo: str,
    inicio_trimestre: date,
    trimestre: int,
    variacao_cambial_trim: Decimal = ZERO,
) -> Decimal:
    base = receita_trim * percentual
    formula = f"{brl(receita_trim)} x {pct(percentual, 1)}"
    if lc224 and inicio_trimestre >= date.fromisoformat(lc224[inicio_acrescimo]):
        limite_trim = D(lc224["receita_anual_isenta"]) / 4
        excedente = max(ZERO, receita_trim - limite_trim)
        if excedente > 0:
            acrescimo = excedente * percentual * D(lc224["acrescimo_relativo"])
            base += acrescimo
            formula += (
                f" + acréscimo LC 224/2025: {brl(excedente)} excedente x {pct(percentual, 1)} x "
                f"{pct(lc224['acrescimo_relativo'], 0)}"
            )
    base_legal = "Lei 9.249/1995, arts. 15 e 20"
    if variacao_cambial_trim:
        base += variacao_cambial_trim
        formula += f" + variação cambial ativa {brl(variacao_cambial_trim)} (100%)"
        base_legal += "; Lei 9.430/1996, art. 25, II (demais receitas e resultados positivos); IN RFB 1.700/2017, art. 215"
    return res.passo(f"{trimestre}º tri - base presumida {tributo}", formula, base, base_legal)


def calcular(perfil: PerfilEmpresa) -> Resultado:
    """Apuração anual = soma de 4 trimestres iguais (receita distribuída uniformemente)."""
    res = Resultado("Lucro Presumido")
    tab = tabelas.vigente("lucro_presumido", date(perfil.ano, 1, 1))
    presuncoes = tabelas.carregar("lucro_presumido")["presuncoes"]
    receita = perfil.receita_bruta_anual

    if receita > D(tab["limite_receita_anual"]):
        res.aplicavel = False
        res.alerta(f"Receita acima de {brl(tab['limite_receita_anual'])}: Lucro Real obrigatório.")
        return res
    if perfil.presuncao not in presuncoes:
        raise ValueError(f"Presunção desconhecida: {perfil.presuncao}")

    p = presuncoes[perfil.presuncao]
    p_irpj, p_csll = D(p["irpj"]), D(p["csll"])
    if perfil.tem_atividades_mistas:
        # Cada atividade tem a presunção própria (Lei 9.249/1995, art. 15); a base é a soma das receitas x percentuais
        partes_txt = []
        soma_irpj = soma_csll = ZERO
        for ativ, valor in perfil.partes_atividade:
            chave = perfil.presuncao if ativ is perfil.atividade else PRESUNCAO_PADRAO[ativ]
            pi, pc = D(presuncoes[chave]["irpj"]), D(presuncoes[chave]["csll"])
            soma_irpj += valor * pi
            soma_csll += valor * pc
            partes_txt.append(f"{presuncoes[chave]['descricao']} {brl(valor)} (IRPJ {pct(pi, 1)}, CSLL {pct(pc, 1)})")
        p_irpj, p_csll = soma_irpj / receita, soma_csll / receita
        res.passo(
            "Percentuais de presunção (atividades mistas, média ponderada pela receita)",
            "; ".join(partes_txt) + f" => IRPJ {pct(p_irpj, 2)}, CSLL {pct(p_csll, 2)}",
            p_irpj,
            "Lei 9.249/1995, art. 15, §1º e art. 20 (percentual de cada atividade)",
        )
    else:
        res.passo(
            "Percentuais de presunção",
            f"{p['descricao']}: IRPJ {pct(p_irpj, 1)}, CSLL {pct(p_csll, 1)}",
            p_irpj,
            "Lei 9.249/1995, art. 15, §1º e art. 20",
        )
    if perfil.presuncao == "servicos_hospitalares":
        res.alerta(
            "Serviços hospitalares (IRPJ 8% e CSLL 12%): a presunção reduzida só vale para quem presta serviços hospitalares e afins na forma da lei "
            "(Lei 9.249/1995, art. 15, § 1º, III, a), em geral por sociedade empresária que atende às exigências da Anvisa. Consultório e clínica "
            "sem esse enquadramento usam 32%. Confirme o enquadramento antes de adotar o percentual."
        )

    lc224 = tab.get("lc224")
    novo = consumo.usa_ibs_cbs(perfil.ano)
    base_receita = consumo.receita_base_irpj(perfil, nao_cumulativo=False) if novo else receita
    if novo:
        res.passo(
            "Receita para IRPJ e CSLL",
            f"{brl(receita)} sem PIS/Cofins, CBS e IBS (e sem o ICMS/ISS já retirado pela transição)",
            base_receita,
            "Lei 9.249/1995, art. 15 (receita bruta); IBS e CBS fora da receita bruta é tese, sem decisão judicial",
        )
    receita_trim = base_receita / 4
    cambial_trim = max(ZERO, perfil.variacao_cambial_anual) / 4
    limite_adicional = D(tab["irpj_adicional_limite_trimestral"])
    irpj_total = csll_total = ZERO
    for t in range(1, 5):
        inicio = date(perfil.ano, 3 * t - 2, 1)
        base_irpj = _base_presumida(res, "IRPJ", receita_trim, p_irpj, lc224, "irpj_inicio", inicio, t, cambial_trim)
        irpj = base_irpj * D(tab["irpj_aliquota"])
        adicional = max(ZERO, base_irpj - limite_adicional) * D(tab["irpj_adicional_aliquota"])
        irpj_total += res.passo(
            f"{t}º tri - IRPJ",
            f"{brl(base_irpj)} x {pct(tab['irpj_aliquota'], 0)} + adicional "
            f"{pct(tab['irpj_adicional_aliquota'], 0)} sobre o que exceder {brl(limite_adicional)}",
            irpj + adicional,
            "Lei 9.430/1996, arts. 3º e 4º",
        )
        base_csll = _base_presumida(res, "CSLL", receita_trim, p_csll, lc224, "csll_inicio", inicio, t, cambial_trim)
        csll_total += res.passo(
            f"{t}º tri - CSLL",
            f"{brl(base_csll)} x {pct(tab['csll_aliquota'], 0)}",
            base_csll * D(tab["csll_aliquota"]),
            "Lei 7.689/1988, art. 3º",
        )

    res.tributos["IRPJ"] = irpj_total
    res.tributos["CSLL"] = csll_total
    if novo:
        consumo.lancar_ibs_cbs(perfil, res, nao_cumulativo=False)
    else:
        interna = perfil.receita_interna_anual
        res.tributos["PIS"] = res.passo(
            "PIS cumulativo", f"{brl(interna)} x {pct(tab['pis_cumulativo'])}",
            interna * D(tab["pis_cumulativo"]),
            "Lei 9.715/1998; exportação: Lei 10.637/2002, art. 5º" if perfil.receita_exterior_anual else "Lei 9.715/1998",
        )
        res.tributos["Cofins"] = res.passo(
            "Cofins cumulativa", f"{brl(interna)} x {pct(tab['cofins_cumulativo'])}",
            interna * D(tab["cofins_cumulativo"]),
            "Lei 9.718/1998; exportação: Lei 10.833/2003, art. 6º" if perfil.receita_exterior_anual else "Lei 9.718/1998",
        )
    tributo_sobre_receita_local(perfil, res)
    res.tributos["INSS patronal"] = inss_patronal_regime_normal(perfil, res)

    alerta_exportacao(perfil, res)
    if novo:
        consumo.alertas(perfil, res)
    if perfil.variacao_cambial_anual > 0:
        res.alerta(
            "Variação cambial ativa somada à base de IRPJ e CSLL (100%, sem a presunção). A Receita entende que o regime "
            "de caixa do art. 30 da MP 2.158-35/2001 se aplica só ao Lucro Real, mas há quem defenda o contrário; "
            "confirme o regime de reconhecimento (caixa ou competência) com o contador. Fora de PIS/Cofins (receita financeira)."
        )
    elif perfil.variacao_cambial_anual < 0:
        res.alerta(
            "Variação cambial passiva (perda) não reduz a base do Lucro Presumido, porque as despesas são presumidas; "
            "o Lucro Real pode aproveitá-la."
        )
    if lc224 and receita > D(lc224["receita_anual_isenta"]):
        res.alerta(
            "Aplicado o acréscimo de 10% na presunção (LC 224/2025) sobre a receita acima de R$ 5 mi/ano. "
            "A regra é questionada no STF (ADIs 7920 e 7936) e há liminares afastando-a; confirme a situação do cliente."
        )
    return res
