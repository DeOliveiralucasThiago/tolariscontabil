from datetime import date
from decimal import Decimal

import pytest

from tolaris_motor import recuperacao
from tolaris_motor.recuperacao import Item, MesBase, classificar, estimar

D = Decimal
JAN_2026 = date(2026, 1, 1)


# --- Classificação -------------------------------------------------------------------------
@pytest.mark.parametrize(
    "item, mono, grupo, st",
    [
        # Refrigerante revendido (NCM 2202.10.00), nota sem marcação: pelo NCM; sem sinal de ST
        (Item("22021000", "5102", "102", "49"), "ncm", "bebidas_frias", None),
        # Mesma bebida, CSOSN 500 / CFOP 5405: ICMS já cobrado por ST
        (Item("22021000", "5405", "500", "49", "0300100"), "ncm", "bebidas_frias", "nota"),
        # CST PIS 04 na própria nota vale mesmo sem NCM na lista
        (Item("10063011", "5102", "102", "04"), "nota", None, None),
        # Venda de produção própria (5101) e remessa (5949) não entram
        (Item("22021000", "5101", "500", "04"), None, None, None),
        (Item("22021000", "5949", "500", "04"), None, None, None),
        # Item com CEST, mas sem sinal de ST na nota: só "a verificar"
        (Item("19059090", "5102", "102", "49", "1700100"), None, None, "cest"),
        # CFOP 6404 indica ST retido anteriormente mesmo com CSOSN genérico
        (Item("19059090", "6404", "102", "49"), None, None, "nota"),
        # Substituto: CSOSN 201 e CST 60/10
        (Item("19059090", "5403", "201", "49"), None, None, "nota"),
        (Item("19059090", "5102", "60", "49"), None, None, "nota"),
        # Autopeça é lista parcial; diesel (prefixo mais longo) vence o grupo genérico 2710.19
        (Item("87089990", "5102", "102", "49"), "verificar", "autopecas", None),
        (Item("27101921", "5656", "500", "49"), "ncm", "diesel", "nota"),
        (Item("27101931", "5656", "500", "49"), "verificar", "outros_derivados", "nota"),
        # Medicamento e cosmético
        (Item("30049099", "5102", "102", "49"), "ncm", "medicamentos", None),
        (Item("33049910", "5102", "102", "49"), "ncm", "perfumaria", None),
        # Pontuação e espaços no NCM não atrapalham
        (Item("3004.90.99", "5102", "102", "49"), "ncm", "medicamentos", None),
        (Item(None, None, None, None), None, None, None),
    ],
)
def test_classificar(item, mono, grupo, st):
    c = classificar(item, JAN_2026)
    assert (c.mono, c.grupo, c.st) == (mono, grupo, st)


# --- Estimativa ----------------------------------------------------------------------------
def _meses(inicio_ano: int, inicio_mes: int, n: int, receita: int, **ultimo) -> list[MesBase]:
    """n meses seguidos com a mesma receita; ``ultimo`` vale só para o último mês."""
    lista = []
    for i in range(n):
        indice = inicio_ano * 12 + inicio_mes - 1 + i
        comp = f"{indice // 12:04d}-{indice % 12 + 1:02d}"
        extra = ultimo if i == n - 1 else {}
        lista.append(MesBase(comp, D(receita), **{k: D(v) for k, v in extra.items()}))
    return lista


def test_estimativa_anexo_i_com_12_meses_de_historico():
    # Receita de R$ 100.000 por mês: RBT12 de jan/2026 = 1.200.000 (4ª faixa do Anexo I)
    # alíquota efetiva = (1.200.000 x 10,7% - 22.500) / 1.200.000 = 8,825%
    # PIS 2,76% + Cofins 12,74% = 15,5% do DAS; ICMS = 33,5% do DAS
    r = estimar(_meses(2025, 1, 13, 100_000, mono_nota=6_000, mono_ncm=4_000, st_nota=20_000,
                       mono_verificar=5_000, st_cest=1_000))
    jan = r.meses[-1]
    assert jan.competencia == "2026-01" and jan.calculado and not jan.rbt12_estimado
    assert jan.rbt12 == D(1_200_000) and jan.faixa == 4
    assert jan.aliquota_efetiva == D("0.08825")
    assert jan.pis_cofins == D("136.79")        # 10.000 x 8,825% x 15,5% = 136,7875
    assert jan.icms == D("591.28")              # 20.000 x 8,825% x 33,5% = 591,275
    assert jan.a_verificar == D("97.96")        # 68,39375 + 29,56375 = 97,9575
    assert r.pis_cofins == D("136.79") and r.icms == D("591.28") and r.provavel == D("728.07")
    # Meses sem item identificado não geram valor
    assert all(m.provavel == 0 for m in r.meses[:-1])
    # Economia anual: soma dos últimos 12 meses (só jan/2026 tem valor) / 12 x 12
    assert r.economia_anual == D("728.07")
    assert r.resultado.tributos["PIS/Cofins pagos a mais (produtos monofásicos)"] == D("136.79")
    assert any("Indício" in a for a in r.resultado.alertas)
    assert any("97,96" in a for a in r.resultado.alertas)


def test_rbt12_estimado_quando_o_historico_e_curto():
    # Só 3 meses importados de R$ 100.000: RBT12 estimado = média x 12 = 1.200.000
    r = estimar(_meses(2026, 1, 3, 100_000, mono_ncm=10_000))
    mar = r.meses[-1]
    assert mar.rbt12 == D(1_200_000) and mar.rbt12_estimado
    assert mar.pis_cofins == D("136.79")
    assert any("RBT12" in a for a in r.resultado.alertas)


def test_faixa_6_nao_tem_icms_no_das():
    # RBT12 de 4.800.000 (6ª faixa do Anexo I): alíquota (4.800.000 x 19% - 378.000) / 4.800.000 = 11,125%
    # PIS 6,13% + Cofins 28,27% = 34,4%; ICMS fora do DAS
    r = estimar(_meses(2025, 1, 13, 400_000, mono_nota=10_000, st_nota=10_000))
    jan = r.meses[-1]
    assert jan.faixa == 6 and jan.aliquota_efetiva == D("0.11125")
    assert jan.pis_cofins == D("382.70")        # 10.000 x 11,125% x 34,4%
    assert jan.icms == D(0)
    assert any("fora do DAS" in a for a in r.resultado.alertas)


def test_rbt12_acima_do_limite_e_ignorado():
    r = estimar(_meses(2025, 1, 13, 500_000, mono_nota=10_000))
    assert not r.meses[-1].calculado and r.provavel == D(0)
    assert any("acima do limite" in a for a in r.resultado.alertas)


def test_anexo_de_servico_nao_se_aplica():
    with pytest.raises(ValueError):
        estimar([MesBase("2026-01", D(1000))], anexo="III")


def test_anexo_do_cliente():
    assert recuperacao.anexo_do_cliente("comercio") == "I"
    assert recuperacao.anexo_do_cliente("industria") == "II"
    assert recuperacao.anexo_do_cliente("servico_anexo_iii") is None
    assert recuperacao.anexo_do_cliente(None) is None


def test_sem_dados():
    r = estimar([])
    assert r.provavel == D(0) and r.economia_anual == D(0) and r.meses == []
