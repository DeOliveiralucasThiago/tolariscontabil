"""Leitura de planilhas de dados contábeis (CSV e XLSX): formatos de número e data, mapeamento e limites."""

from __future__ import annotations

import io
import zipfile

import pytest
from openpyxl import Workbook

from tolaris_api import planilha as pl


def _xlsx(linhas: list[list]) -> bytes:
    wb = Workbook()
    ws = wb.active
    for l in linhas:
        ws.append(l)
    saida = io.BytesIO()
    wb.save(saida)
    return saida.getvalue()


@pytest.mark.parametrize("texto,esperado", [
    ("1.234,56", 123456), ("1234,56", 123456), ("1234.56", 123456), ("R$ 1.234,56", 123456),
    ("1,234.56", 123456), ("1.234", 123400), ("1234", 123400), ("0,5", 50), ("", None), ("-", None), ("  ", None),
])
def test_parse_dinheiro(texto, esperado):
    assert pl.parse_dinheiro(texto) == esperado


@pytest.mark.parametrize("texto", ["-100,00", "(100,00)", "abc", "1,2,3", "999999999999,00"])
def test_parse_dinheiro_rejeita(texto):
    with pytest.raises(ValueError):
        pl.parse_dinheiro(texto)


@pytest.mark.parametrize("texto,esperado", [
    ("2026-03", "2026-03"), ("03/2026", "2026-03"), ("3/2026", "2026-03"), ("01/03/2026", "2026-03"),
    ("2026-03-15", "2026-03"), ("2026-03-15T00:00:00", "2026-03"), ("mar/26", "2026-03"), ("Março/2026", "2026-03"),
    ("DEZ/2025", "2025-12"), ("13/2026", None), ("2026-13", None), ("abc", None), ("", None), ("1999-01", None),
])
def test_parse_competencia(texto, esperado):
    assert pl.parse_competencia(texto) == esperado


def test_csv_com_ponto_e_virgula_bom_e_acentos():
    conteudo = pl.modelo_csv()
    cab, linhas = pl.ler_tabela("modelo.csv", conteudo)
    assert cab[0] == "Competência" and len(linhas) == 2 and linhas[0][1] == "120000,00"


def test_csv_cp1252_e_virgula_como_separador():
    texto = "Mês,Faturamento\n2026-01,\"1.000,00\"\n".encode("cp1252")
    cab, linhas = pl.ler_tabela("a.csv", texto)
    assert cab == ["Mês", "Faturamento"] and linhas == [["2026-01", "1.000,00"]]


def test_xlsx_com_numeros_e_datas():
    from datetime import date

    cab, linhas = pl.ler_tabela("a.xlsx", _xlsx([["Mês", "Receita"], [date(2026, 1, 1), 1500.5], [date(2026, 2, 1), 2000]]))
    assert cab == ["Mês", "Receita"]
    assert linhas == [["2026-01-01", "1500.5"], ["2026-02-01", "2000"]]
    r = pl.converter(linhas, {"competencia": 0, "receita": 1})
    assert r.meses == {"2026-01": {"receita": 150050}, "2026-02": {"receita": 200000}}


def test_limites_e_formatos_invalidos():
    with pytest.raises(pl.PlanilhaInvalida, match="MB"):
        pl.ler_tabela("a.csv", b"x" * (pl.LIMITE_BYTES + 1))
    with pytest.raises(pl.PlanilhaInvalida, match="csv ou .xlsx"):
        pl.ler_tabela("a.pdf", b"abc")
    with pytest.raises(pl.PlanilhaInvalida, match="cabeçalho"):
        pl.ler_tabela("a.csv", b"so,cabecalho\n")
    with pytest.raises(pl.PlanilhaInvalida, match="xlsx válida"):
        pl.ler_tabela("a.xlsx", b"nao sou zip")
    muitas = "mes;receita\n" + "\n".join(f"2026-01;{i}" for i in range(pl.LIMITE_LINHAS + 1))
    with pytest.raises(pl.PlanilhaInvalida, match="linhas"):
        pl.ler_tabela("a.csv", muitas.encode())


def test_xlsx_bomba_de_descompactacao(monkeypatch):
    monkeypatch.setattr(pl, "LIMITE_DESCOMPACTADO", 100)
    with pytest.raises(pl.PlanilhaInvalida, match="descompactada"):
        pl.ler_tabela("a.xlsx", _xlsx([["a", "b"], [1, 2]]))


def test_sugestao_de_colunas_pelo_cabecalho():
    cab = ["Mês/Ano", "Faturamento Bruto", "Custo das Mercadorias", "Folha de Pagamento", "Pró-labore", "Despesas Creditáveis", "Outras Despesas"]
    s = pl.sugerir_mapeamento(cab)
    assert s == {"competencia": 0, "receita": 1, "compras": 2, "folha": 3, "pro_labore": 4, "despesas_creditaveis": 5, "outras_despesas": 6}


def test_sugestao_nao_repete_coluna_e_deixa_vazio_o_que_nao_acha():
    s = pl.sugerir_mapeamento(["Período", "Vendas", "Observações"])
    assert s["competencia"] == 0 and s["receita"] == 1 and s["folha"] is None and s["compras"] is None
    assert len({v for v in s.values() if v is not None}) == 2


def test_validar_mapeamento():
    assert pl.validar_mapeamento({"competencia": 0, "receita": 1, "folha": None}, 3) == {"competencia": 0, "receita": 1}
    for ruim, msg in (({"receita": 1}, "competência"), ({"competencia": 0}, "valores"),
                      ({"competencia": 0, "receita": 5}, "fora"), ({"competencia": 0, "receita": 0}, "mesma coluna"),
                      ({"competencia": 0, "receita": "1"}, "fora")):
        with pytest.raises(pl.PlanilhaInvalida, match=msg):
            pl.validar_mapeamento(ruim, 3)


def test_converter_ignora_linhas_ruins_e_soma_meses_repetidos():
    linhas = [["2026-01", "1.000,00", "10,00"], ["2026-01", "500,00", ""], ["xx", "1,00", ""], ["2026-02", "-5,00", ""],
              ["2026-03", "", ""]]
    r = pl.converter(linhas, {"competencia": 0, "receita": 1, "folha": 2})
    assert r.meses["2026-01"] == {"receita": 150000, "folha": 1000}
    assert r.meses["2026-03"] == {"receita": None, "folha": None}
    assert "2026-02" not in r.meses
    assert [n for n, _ in r.ignoradas] == [4, 5]
    assert "2026-01" in r.avisos[0]
