"""O kit dos testadores (scripts/gerar_kit_teste.py) tem de entrar no sistema do jeito que o roteiro descreve."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

RAIZ = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def kit(tmp_path_factory) -> Path:
    spec = importlib.util.spec_from_file_location("gerar_kit_teste", RAIZ / "scripts" / "gerar_kit_teste.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    pasta = tmp_path_factory.mktemp("kit")
    mod.SAIDA = pasta
    mod.main()
    return pasta


def _arquivo(kit: Path, nome: str) -> tuple[str, bytes]:
    return nome, (kit / nome).read_bytes()


def _lote(c: TestClient, caminho: str, kit: Path, nome: str, mapa: dict, **campos):
    return c.post(f"/api/clientes-lote/{caminho}", files=[("arquivos", _arquivo(kit, nome))],
                  data={"mapeamento": json.dumps(mapa), **campos})


def test_clientes_para_importar(logado: TestClient, kit: Path):
    previa = logado.post("/api/clientes-lote/previa", files=[("arquivos", _arquivo(kit, "1-clientes-para-importar.xlsx"))]).json()
    mapa = previa["sugestao"]
    assert mapa["cnpj"] == 0 and mapa["razao_social"] == 1 and mapa["atividade"] == 2 and mapa["regime_atual"] == 3
    analise = _lote(logado, "analisar", kit, "1-clientes-para-importar.xlsx", mapa).json()
    assert (analise["novos"], analise["invalidos"], analise["repetidos"]) == (9, 1, 1)
    assert _lote(logado, "importar", kit, "1-clientes-para-importar.xlsx", mapa).status_code == 201
    clientes = {c["cnpj"]: c for c in logado.get("/api/clientes").json()}
    mercadinho = clientes["12345678000195"]
    assert (mercadinho["razao_social"], mercadinho["atividade"], mercadinho["regime_atual"]) == ("Mercadinho Estrela Ltda", "comercio", "simples")
    aurora = clientes["98765432000198"]
    assert (aurora["razao_social"], aurora["atividade"], aurora["regime_atual"]) == ("Consultoria Aurora Ltda", "servico_fator_r", "simples")
    assert logado.get("/api/clientes-lote/pendentes").json() == {"pendentes": 7}


def _cliente_estrela(logado: TestClient) -> int:
    return logado.post("/api/clientes", json={"razao_social": "Mercadinho Estrela Ltda", "cnpj": "12345678000195",
                                              "atividade": "comercio", "regime_atual": "simples"}).json()["id"]


def test_dados_contabeis(logado: TestClient, kit: Path):
    cid = _cliente_estrela(logado)
    previa = logado.post(f"/api/clientes/{cid}/financeiro/previa", files=[("arquivos", _arquivo(kit, "2-dados-contabeis-12-meses.xlsx"))]).json()
    assert previa["total_linhas"] == 12
    mapa = previa["sugestao"]
    assert all(mapa[k] is not None for k in ("competencia", "receita", "compras", "folha", "pro_labore", "despesas_creditaveis", "outras_despesas"))
    r = logado.post(f"/api/clientes/{cid}/financeiro/importar", files=[("arquivos", _arquivo(kit, "2-dados-contabeis-12-meses.xlsx"))],
                    data={"mapeamento": json.dumps(mapa)})
    assert r.status_code == 201, r.text
    estado = logado.get(f"/api/clientes/{cid}/financeiro").json()
    assert len(estado["meses"]) == 12 and estado["planejamento"]["meses"] == 12 and not estado["planejamento"]["anualizado"]
    assert estado["planejamento"]["periodo_inicio"] == "2025-10" and estado["planejamento"]["periodo_fim"] == "2026-09"


def test_notas_sped_e_imposto_pago_a_mais(logado: TestClient, kit: Path):
    cid = _cliente_estrela(logado)
    enviar = lambda nome: logado.post(f"/api/clientes/{cid}/importacoes", files=[("arquivos", _arquivo(kit, nome))]).json()
    r = enviar("3-notas-xml.zip")
    assert r["importados"] == 33 and r["duplicados"] == 0 and len(r["competencias"]) == 11
    motivos = {i["arquivo"].split("/")[-1]: i["motivo"] for i in r["ignorados"]}
    assert set(motivos) == {"nota-cancelada.xml", "nota-de-outra-empresa.xml", "nao-e-nota.xml"}
    assert "não autorizada" in motivos["nota-cancelada.xml"] and "nem destinatário" in motivos["nota-de-outra-empresa.xml"]
    assert enviar("3-notas-xml.zip")["duplicados"] == 33  # reimportar não soma de novo

    s = enviar("4-sped-fiscal-2026-09.txt")
    assert s["importados"] == 6 and s["competencias"] == ["2026-09"]

    mov = logado.get(f"/api/clientes/{cid}/movimento").json()
    assert len(mov["meses"]) == 12 and mov["receita_12m"] > 500_000

    rec = logado.get(f"/api/clientes/{cid}/recuperacao").json()
    assert rec["disponivel"] and rec["totais"]["provavel"] > 0


def test_apoio_do_enquadramento(logado: TestClient, kit: Path):
    """O arquivo 5-enquadramento-apoio.txt promete números e CNAEs; a ferramenta tem de entregá-los."""
    texto = (kit / "5-enquadramento-apoio.txt").read_text(encoding="utf-8")
    for trecho in ("R$ 600.000,00", "R$ 36.000,00", "R$ 60.000,00", "6,00%", "11.000,00"):
        assert trecho in texto
    d = logado.post("/api/calculadoras/enquadramento", json={
        "atividade": "servico_fator_r", "receita_bruta_anual": 600000, "pro_labore_anual": 36000, "outras_despesas_anual": 60000,
        "percentual_anexo_iii": 0.3}).json()
    assert d["fator_r_atual"] == 0.06
    assert d["cenarios"][0]["anexos_simples"] == ["V"]
    assert "R$ 11.000,00/mês" in d["cenarios"][1]["descricao"]
    assert "anexo_iii_30" in [c["chave"] for c in d["cenarios"]]

    esperado = {  # código: (trecho do Anexo, selo, vedação)
        "6201501": ("Anexo III ou V (fator R)", "tabela", None),
        "7020400": ("Anexo III ou V (fator R)", "tabela", None),
        "6911701": ("Anexo IV", "tabela", None),
        "6421200": ("Vedado ao Simples", "oficial", "impeditivo"),
        "4781400": ("Anexo I (comércio)", "tabela", None),
        "6920601": ("Anexo III", "divisao", None),
    }
    for codigo, (anexo, selo, vedacao) in esperado.items():
        assert f"{codigo[:4]}-{codigo[4]}/{codigo[5:]}" in texto
        item = logado.get(f"/api/cnae/{codigo}").json()
        assert (item["anexo"], item["confianca"], item["vedacao"]) == (anexo, selo, vedacao), codigo


def test_planilha_de_validacao_vai_no_kit(kit: Path):
    import openpyxl

    wb = openpyxl.load_workbook(kit / "6-casos-de-validacao.xlsx")
    codigos = {linha[0] for linha in wb["Casos"].iter_rows(min_row=2, values_only=True)}
    assert {f"ENQ{i}" for i in range(1, 7)} <= codigos and {"SR4-2028", "SR6-2032"} <= codigos
    assert "85 casos" in wb["Instruções"]["A2"].value
    leia_me = (kit / "LEIA-ME.txt").read_text(encoding="utf-8")
    assert "6-casos-de-validacao.xlsx" in leia_me and "ENQ1" in leia_me
