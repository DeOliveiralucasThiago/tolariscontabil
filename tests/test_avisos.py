from datetime import date
from decimal import Decimal

import pytest

from tolaris_motor import Atividade, PerfilEmpresa, avisos, pessoa_fisica

D = Decimal
JAN_2026 = date(2026, 1, 1)


def _fator_r(pro_labore: int, **extra) -> PerfilEmpresa:
    return PerfilEmpresa(Atividade.SERVICO_FATOR_R, 600_000, folha_clt_anual=96_000, pro_labore_anual=pro_labore, **extra)


def test_fator_r_abaixo_do_minimo_com_ganho():
    # Folha = 96.000 + 60.000 + FGTS 7.680 = 163.680 -> fator R 27,28%
    # Falta 600.000 x 28% - 163.680 = 4.320/ano = R$ 360/mês de pró-labore
    # DAS Anexo V: 600.000 x (600.000 x 19,5% - 9.900) / 600.000 = 107.100
    # DAS Anexo III: 600.000 x 10,56% = 63.360  -> diferença 43.740
    # INSS do sócio: 11% x (5.360 - 5.000) x 12 = 475,20  -> ganho líquido 43.264,80
    a = avisos.avaliar_fator_r(_fator_r(60_000))
    assert a.codigo == "fator_r_abaixo" and a.gravidade == "oportunidade"
    assert a.valor == D("43264.80")
    assert "27,28%" in a.titulo and "R$ 360,00" in a.detalhe and "R$ 107.100,00" in a.detalhe
    assert "R$ 63.360,00" in a.detalhe and "R$ 475,20" in a.detalhe


def test_fator_r_perto_do_minimo():
    # Folha 96.000 + 72.000 + 7.680 = 175.680 -> 29,28%; sobram 175.680 - 168.000 = 7.680
    a = avisos.avaliar_fator_r(_fator_r(72_000))
    assert a.codigo == "fator_r_margem" and a.gravidade == "atencao"
    assert a.valor == D("43740.00")             # DAS V - DAS III se cair para o Anexo V
    assert "R$ 7.680,00" in a.detalhe


def test_fator_r_folgado_ou_outra_atividade_nao_gera_aviso():
    assert avisos.avaliar_fator_r(_fator_r(200_000)) is None          # 43,3%
    comercio = PerfilEmpresa(Atividade.COMERCIO, 600_000, folha_clt_anual=10_000)
    assert avisos.avaliar_fator_r(comercio) is None
    assert avisos.avaliar_fator_r(PerfilEmpresa(Atividade.SERVICO_FATOR_R, 5_000_000)) is None  # fora do Simples


def test_fator_r_quando_aumentar_pro_labore_nao_compensa(monkeypatch):
    monkeypatch.setattr(pessoa_fisica, "inss_contribuinte_individual",
                        lambda rem, data, aliquota=None: D(rem) * D("500"))   # custo absurdo de INSS
    a = avisos.avaliar_fator_r(_fator_r(60_000))
    assert a.gravidade == "info" and a.valor == D(0) and "não compensa" in a.titulo


def _codigos(lista):
    return {a.codigo: a.gravidade for a in lista}


@pytest.mark.parametrize(
    "rbt12, esperado",
    [
        (50_000, {}),
        (70_000, {"mei_limite": "atencao"}),        # 86% do limite de 81.000
        (78_000, {"mei_limite": "critico"}),        # 96%
        (85_000, {"mei_limite": "critico"}),        # acima, dentro dos 20%
        (100_000, {"mei_limite": "critico"}),       # acima de 97.200: retroativo
    ],
)
def test_limites_do_mei(rbt12, esperado):
    assert _codigos(avisos.avaliar_limites(rbt12, "mei", JAN_2026)) == esperado


def test_mei_mensagens():
    dentro = avisos.avaliar_limites(85_000, "mei", JAN_2026, fonte="notas de jan/25 a dez/25")[0]
    assert "acima do limite do MEI" in dentro.titulo and "R$ 97.200,00" in dentro.detalhe
    assert "notas de jan/25 a dez/25" in dentro.detalhe
    retro = avisos.avaliar_limites(100_000, "mei", JAN_2026)[0]
    assert "desenquadrado" in retro.titulo and "desde 1º de janeiro" in retro.detalhe


@pytest.mark.parametrize(
    "rbt12, esperado",
    [
        (1_000_000, {}),
        (2_900_000, {"simples_sublimite": "atencao"}),                                   # 80,6% do sublimite de 3,6 mi
        (3_500_000, {"simples_sublimite": "atencao"}),                                   # 97%
        (4_000_000, {"simples_sublimite": "atencao", "simples_limite": "atencao"}),      # acima do sublimite; 83% do limite
        (4_700_000, {"simples_sublimite": "atencao", "simples_limite": "critico"}),      # 97,9% do limite
        (5_000_000, {"simples_sublimite": "atencao", "simples_limite": "critico"}),      # acima do limite
    ],
)
def test_limites_do_simples(rbt12, esperado):
    assert _codigos(avisos.avaliar_limites(rbt12, "simples", JAN_2026)) == esperado


def test_simples_acima_do_limite_cita_a_tolerancia():
    a = {x.codigo: x for x in avisos.avaliar_limites(5_000_000, "simples", JAN_2026)}["simples_limite"]
    assert "R$ 5.760.000,00" in a.detalhe and "retroativa" in a.detalhe


@pytest.mark.parametrize(
    "rbt12, esperado",
    [
        (1_000_000, {}),
        (4_500_000, {"presumido_lc224": "atencao"}),                                    # 90% de 5 mi
        (6_000_000, {"presumido_lc224": "atencao"}),                                    # acima: presunção +10%
        (80_000_000, {"presumido_lc224": "atencao", "presumido_limite": "critico"}),    # acima de 78 mi
    ],
)
def test_limites_do_presumido(rbt12, esperado):
    assert _codigos(avisos.avaliar_limites(rbt12, "presumido", JAN_2026)) == esperado


def test_limites_sem_regime_ou_sem_receita():
    assert avisos.avaliar_limites(4_000_000, None, JAN_2026) == []
    assert avisos.avaliar_limites(4_000_000, "real", JAN_2026) == []
    assert avisos.avaliar_limites(0, "simples", JAN_2026) == []


def test_lc224_antes_de_2026_nao_gera_aviso():
    codigos = _codigos(avisos.avaliar_limites(6_000_000, "presumido", date(2025, 6, 1)))
    assert "presumido_lc224" not in codigos
