from decimal import Decimal

import pytest

from tolaris_motor import reforma_simples as rs, simples
from datetime import date

D = Decimal


def entrada(**kw):
    base = dict(atividade="servico_anexo_iii", receita_bruta_anual=120_000, percentual_b2b=1)
    base.update(kw)
    return rs.EntradaSimplesReforma(**base)


def test_partilha_soma_100_e_teto_do_iss():
    for anexo in ("I", "II", "III", "IV", "V"):
        for rbt in (100_000, 500_000, 2_000_000, 4_000_000):
            assert sum(simples.partilha(anexo, rbt, date(2026, 1, 1)).values()) == pytest.approx(D(1))
    # Anexo III, 5ª faixa com RBT12 de 3 mi: 16,812% x 33,5% = 5,63% > 5% -> ISS limitado a 5%
    p = simples.partilha("III", 3_000_000, date(2026, 1, 1))
    assert p["iss"] * simples.aliquota_efetiva("III", 3_000_000, date(2026, 1, 1)) == pytest.approx(D("0.05"))


def test_2033_so_b2b_sem_compras():
    c = {x.ano: x for x in rs.simular(entrada())}[2033]
    e, s, a = D("0.06"), D("0.0278") + D("0.1282") + D("0.335"), D("0.265")
    assert c.dentro_do_das == 120_000 * (1 - e)
    assert c.por_fora == pytest.approx(120_000 * (1 - e * s) * (1 - e * (1 - s)))
    assert c.credito_cliente_dentro == pytest.approx(100 * e * s)
    assert c.credito_cliente_fora == pytest.approx(100 * a)


def test_2027_substitui_so_pis_cofins_com_cbs():
    c = {x.ano: x for x in rs.simular(entrada(percentual_b2b=0))}[2027]
    e, s, a = D("0.06"), D("0.0278") + D("0.1282"), D("0.087") + D("0.001")
    assert c.por_fora == pytest.approx(120_000 * (1 - e * (1 - s)) / (1 + a))
    assert c.diferenca < 0
    assert c.recomendacao.startswith("Manter")


def test_creditos_nas_compras_favorecem_por_fora():
    sem = rs.simular(entrada(atividade="comercio", receita_bruta_anual=2_000_000, percentual_b2b="0.8"))[1]
    com = rs.simular(entrada(atividade="comercio", receita_bruta_anual=2_000_000, percentual_b2b="0.8",
                             compras_creditaveis_anual=1_200_000))[1]
    assert com.por_fora - sem.por_fora == pytest.approx(1_200_000 * D("0.265"))
    assert com.recomendacao.startswith("Recolher")


def test_ponto_de_equilibrio_iguala_cenarios():
    c = rs.simular(entrada(compras_creditaveis_anual=20_000))[1]
    assert c.equilibrio_b2b is not None
    no_ponto = rs.simular(entrada(compras_creditaveis_anual=20_000, percentual_b2b=c.equilibrio_b2b))[1]
    assert no_ponto.diferenca == pytest.approx(0, abs=D("0.01"))


def test_curva_b2b_crescente():
    curva = rs.curva_b2b(entrada(), 2033)
    assert len(curva) == 11 and curva[0][0] == 0 and curva[-1][0] == 1
    difs = [d for _, d in curva]
    assert difs == sorted(difs)


def test_validacoes():
    with pytest.raises(ValueError):
        entrada(percentual_b2b=2)
    with pytest.raises(ValueError):
        entrada(anos=[2030])


def test_ipi_da_industria_nao_e_substituido_em_2033():
    # Res. CGSN 190/2026, Anexo II (2033): CBS 14% + IBS 32% da faixa; o IPI de 7,5% permanece
    assert "ipi" not in rs.SUBSTITUIDOS[2033]
    r = next(x for x in rs.simular(entrada(atividade="industria", receita_bruta_anual=120_000)) if x.ano == 2033)
    passos = [p for p in r.resultado.memoria if p.descricao.startswith("Alíquota da fatia")]
    assert passos and passos[0].valor == pytest.approx(D("0.1151") + D("0.0249") + D("0.32"))  # 46,0% do DAS
    assert any("Res. CGSN 190/2026" in a for a in r.resultado.alertas)
    assert any("01/09 a 30/10/2026" in a and "20/12/2026" in a for a in r.resultado.alertas)
