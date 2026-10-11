from datetime import date
from decimal import Decimal

import pytest

from tolaris_motor import Atividade, PerfilEmpresa, simples

D = Decimal
HOJE = date(2026, 1, 1)


@pytest.mark.parametrize(
    "anexo, rbt12, esperado",
    [
        # 1ª faixa: alíquota nominal
        ("I", 120_000, D("0.04")),
        ("III", 180_000, D("0.06")),
        # Anexo III, 3ª faixa: (500.000 x 13,5% - 17.640) / 500.000 = 9,972%
        ("III", 500_000, D("0.09972")),
        # Anexo I, 4ª faixa: (1.000.000 x 10,7% - 22.500) / 1.000.000 = 8,45%
        ("I", 1_000_000, D("0.0845")),
        # Anexo II, 2ª faixa: (300.000 x 7,8% - 5.940) / 300.000 = 5,82%
        ("II", 300_000, D("0.0582")),
        # Anexo V, 3ª faixa: (600.000 x 19,5% - 9.900) / 600.000 = 17,85%
        ("V", 600_000, D("0.1785")),
        # Anexo IV, 5ª faixa: (2.400.000 x 22% - 183.780) / 2.400.000 = 14,3425%
        ("IV", 2_400_000, D("0.143425")),
        # Limite exato da faixa fica na faixa (até 360.000 é 2ª faixa)
        ("III", 360_000, (D(360_000) * D("0.112") - 9360) / 360_000),
    ],
)
def test_aliquota_efetiva(anexo, rbt12, esperado):
    assert simples.aliquota_efetiva(anexo, rbt12, HOJE) == esperado


def test_aliquota_inicio_de_atividade_usa_nominal():
    assert simples.aliquota_efetiva("III", 0, HOJE) == D("0.06")


def test_faixa_acima_do_limite():
    with pytest.raises(ValueError):
        simples.faixa("I", 4_800_000.01, HOJE)


def test_fator_r_define_anexo_iii():
    p = PerfilEmpresa(Atividade.SERVICO_FATOR_R, 600_000, pro_labore_anual=168_000)
    assert simples.anexo_da_atividade(p) == "III"


def test_fator_r_inclui_fgts_e_define_anexo_v():
    # 96.000 + 60.000 + 7.680 (FGTS) = 163.680 / 600.000 = 27,28% < 28%
    p = PerfilEmpresa(Atividade.SERVICO_FATOR_R, 600_000, folha_clt_anual=96_000, pro_labore_anual=60_000)
    assert simples.folha_fator_r(p) == D("163680.00")
    assert simples.anexo_da_atividade(p) == "V"


def test_folha_fator_r_informada_tem_prioridade():
    p = PerfilEmpresa(Atividade.SERVICO_FATOR_R, 600_000, folha_fator_r_anual=200_000)
    assert simples.anexo_da_atividade(p) == "III"


def test_pro_labore_minimo_para_fator_r():
    # 28% de 600.000 = 168.000; faltam 4.320 no ano = 360/mês
    assert simples.pro_labore_minimo_fator_r(600_000, 163_680, HOJE) == D("360")
    assert simples.pro_labore_minimo_fator_r(600_000, 200_000, HOJE) == 0


def test_das_anual_e_alerta_de_fator_r():
    p = PerfilEmpresa(Atividade.SERVICO_FATOR_R, 600_000, folha_clt_anual=96_000, pro_labore_anual=60_000)
    r = simples.calcular(p)
    assert r.tributos["DAS"] == D("107100")
    assert any("360,00/mês" in a for a in r.alertas)


def test_anexo_iv_recolhe_cpp_fora_do_das():
    p = PerfilEmpresa(Atividade.SERVICO_ANEXO_IV, 180_000, folha_clt_anual=50_000, pro_labore_anual=20_000)
    r = simples.calcular(p)
    assert r.tributos["DAS"] == D("8100")  # 4,5%
    # 50.000 x (20% + 2% RAT) + 20.000 x 20% = 11.000 + 4.000
    assert r.tributos["INSS patronal (fora do DAS)"] == D("15000")


def test_receita_acima_do_limite_nao_aplicavel():
    r = simples.calcular(PerfilEmpresa(Atividade.COMERCIO, 5_000_000))
    assert not r.aplicavel
    assert r.total == 0


def test_alerta_sublimite():
    r = simples.calcular(PerfilEmpresa(Atividade.COMERCIO, 4_000_000))
    assert any("sublimite" in a for a in r.alertas)
