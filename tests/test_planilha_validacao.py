"""A planilha de validação do contador (scripts/gerar_planilha_validacao.py) tem de bater com o motor."""

from __future__ import annotations

import importlib.util
import sys
from decimal import Decimal
from pathlib import Path

import openpyxl
import pytest

from tolaris_motor import Atividade, PerfilEmpresa, enquadramento

RAIZ = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def gerador():
    spec = importlib.util.spec_from_file_location("gerar_planilha_validacao", RAIZ / "scripts" / "gerar_planilha_validacao.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod  # o @dataclass do gerador precisa achar o módulo
    spec.loader.exec_module(mod)
    return mod


def test_casos_de_enquadramento_e_simples_na_reforma_intermediarios(gerador, tmp_path):
    casos = {c.codigo: c for c in gerador.casos()}
    assert {f"ENQ{i}" for i in range(1, 7)} <= set(casos)
    assert {"SR4-2028", "SR4-2032", "SR5-2029", "SR6-2032"} <= set(casos)

    # ENQ1 é o caso do kit de teste: fator R de 6%, pró-labore a mais de R$ 11.000/mês
    perfil = PerfilEmpresa(Atividade.SERVICO_FATOR_R, 600_000, pro_labore_anual=36_000, outras_despesas_anual=60_000)
    cenarios = enquadramento.analisar(perfil, "0.3")
    enq1 = casos["ENQ1"].resultado
    assert len(enq1.tributos) == len(cenarios) + 1  # um DAS por cenário e o INSS do cenário do fator R
    assert enq1.tributos["DAS - Como está hoje"] == Decimal("107100")
    assert enq1.tributos["DAS - Pró-labore +R$ 11.000,00/mês (fator R de 28%)"] == Decimal("63360")
    assert casos["ENQ5"].resultado.tributos == {"DAS - Como está hoje": Decimal("63360")}  # já no Anexo III: só o cenário de hoje

    saida = gerador.gerar(tmp_path / "casos.xlsx")
    wb = openpyxl.load_workbook(saida)
    codigos = {linha[0] for linha in wb["Casos"].iter_rows(min_row=2, values_only=True)}
    assert {"ENQ1", "ENQ6", "SR6-2029"} <= codigos
    # alternativas não somam: o Enquadramento não ganha linha de TOTAL
    assert not any(l[0] == "ENQ1" and l[3] == "TOTAL" for l in wb["Casos"].iter_rows(min_row=2, values_only=True))


def test_teto_do_iss_aparece_no_caso_da_5a_faixa(gerador):
    # SR6: Anexo III com receita de R$ 3,0 mi: a partir de 2028 o teto do ISS (5%, 4,5%, 3%) muda a fatia de IBS/CBS
    casos = {c.codigo: c for c in gerador.casos()}
    fatias = {}
    for ano in (2028, 2029, 2032):
        passo = next(p for p in casos[f"SR6-{ano}"].resultado.memoria if p.descricao.startswith("Alíquota da fatia"))
        fatias[ano] = passo.valor
    assert fatias[2028] < fatias[2029] < fatias[2032]
