from datetime import date
from decimal import Decimal

import pytest

from tolaris_motor import pessoa_fisica as pf

D = Decimal
JAN_2026 = date(2026, 1, 1)
JUN_2025 = date(2025, 6, 1)


@pytest.mark.parametrize(
    "salario, esperado",
    [
        (1621, D("121.58")),  # 7,5% (121,575 arredonda para cima)
        # 121,575 + (2.902,84 - 1.621) x 9% + (3.000 - 2.902,84) x 12% = 121,575 + 115,3656 + 11,6592
        (3000, D("248.60")),
        (8475.55, D("988.09")),  # contribuição máxima 2026
        (20000, D("988.09")),  # limitado ao teto
    ],
)
def test_inss_empregado_2026(salario, esperado):
    assert pf.inss_empregado(salario, JAN_2026) == esperado


def test_inss_contribuinte_individual_limitado_ao_teto():
    assert pf.inss_contribuinte_individual(1621, JAN_2026) == D("178.31")
    assert pf.inss_contribuinte_individual(20000, JAN_2026) == D("932.31")  # 8.475,55 x 11%


def test_irpf_2026_isento_ate_5000():
    inss = pf.inss_empregado(5000, JAN_2026)
    assert pf.irpf_mensal(5000, JAN_2026, inss=inss).tributos["IRPF"] == 0


def test_irpf_2026_reducao_parcial():
    # Base = 5.900 - 627,51 (INSS) = 5.272,49; 5.272,49 x 27,5% - 908,73 = 541,20
    # Redução = 978,62 - 0,133145 x 5.900 = 193,06 -> 348,14
    inss = pf.inss_empregado(5900, JAN_2026)
    assert inss == D("627.51")
    assert pf.irpf_mensal(5900, JAN_2026, inss=inss).tributos["IRPF"] == D("348.14")


def test_irpf_2026_sem_reducao_acima_de_7350():
    r = pf.irpf_mensal(10000, JAN_2026, inss=D("988.09"))
    # (10.000 - 988,09) x 27,5% - 908,73 = 1.569,545 -> 1.569,55
    assert r.tributos["IRPF"] == D("1569.55")


def test_irpf_2025_sem_reducao():
    # Mesma renda de 5.000 em 2025 pagava imposto (sem a Lei 15.270)
    # Base = 5.000 - 607,20 (simplificado > INSS 2025 de 518,82) = 4.392,80 -> 4.392,80 x 22,5% - 675,49
    r = pf.irpf_mensal(5000, JUN_2025, inss=pf.inss_empregado(5000, JUN_2025))
    assert r.tributos["IRPF"] == D("312.89")


def test_irpf_usa_desconto_simplificado_quando_maior():
    r = pf.irpf_mensal(3000, JAN_2026, inss=D("100"))
    # 3.000 - 607,20 = 2.392,80 -> isento
    assert r.tributos["IRPF"] == 0


def test_irpf_dependentes():
    sem = pf.irpf_mensal(12000, JAN_2026, inss=D("988.09")).tributos["IRPF"]
    com = pf.irpf_mensal(12000, JAN_2026, inss=D("988.09"), dependentes=2).tributos["IRPF"]
    assert sem - com == pytest.approx(D("189.59") * 2 * D("0.275"), abs=D("0.01"))


@pytest.mark.parametrize(
    "valor, data, esperado",
    [
        (50000, JAN_2026, 0),
        (50000.01, JAN_2026, D("5000.00")),  # 10% sobre o total, não só o excedente
        (80000, JAN_2026, D("8000")),
        (80000, JUN_2025, 0),  # antes da vigência
    ],
)
def test_retencao_dividendos(valor, data, esperado):
    assert pf.retencao_dividendos(valor, data) == esperado


@pytest.mark.parametrize(
    "renda, esperado",
    [(600_000, 0), (900_000, D("0.05")), (1_200_000, D("0.10")), (5_000_000, D("0.10"))],
)
def test_irpfm_aliquota(renda, esperado):
    assert pf.irpfm_aliquota(renda) == esperado


def test_pro_labore_vs_dividendos_presumido():
    a, b = pf.comparar_pro_labore_dividendos(20000, JAN_2026, regime="presumido")
    # Cenário A: INSS 932,31 + IRPF + CPP 4.000
    assert a.resultado.tributos["INSS do sócio (11%)"] == D("932.31")
    assert a.resultado.tributos["INSS patronal (20%)"] == D("4000")
    ir = (D(20000) - D("932.31")) * D("0.275") - D("908.73")
    assert a.resultado.tributos["IRPF sobre pró-labore"] == ir.quantize(D("0.01"))
    # Cenário B: pró-labore = salário mínimo 2026
    assert b.pro_labore == D("1621.00")
    assert b.custo_mensal == D("178.31") + D("324.20")
    assert b.custo_mensal < a.custo_mensal


def test_pro_labore_simples_sem_cpp():
    a, _ = pf.comparar_pro_labore_dividendos(10000, JAN_2026, regime="simples")
    assert "INSS patronal (20%)" not in a.resultado.tributos


def test_pro_labore_real_reduz_irpj():
    a, _ = pf.comparar_pro_labore_dividendos(10000, JAN_2026, regime="real")
    assert a.resultado.tributos["Economia de IRPJ/CSLL (Lucro Real)"] == D("-4080")  # 12.000 x 34%


def test_dividendos_altos_retem_e_alertam_irpfm():
    _, b = pf.comparar_pro_labore_dividendos(100_000, JAN_2026)
    assert b.resultado.tributos["IRRF 10% sobre dividendos"] == D("9837.90")  # (100.000 - 1.621) x 10%
    assert any("IRPFM" in a for a in b.resultado.alertas)
