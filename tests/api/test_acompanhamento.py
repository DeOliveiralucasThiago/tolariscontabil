"""Planejado × realizado, reavaliação da recomendação e avisos de projeção de limite."""

from __future__ import annotations

import json

from fastapi.testclient import TestClient

from .conftest import CNPJ_VALIDO, cadastrar
from .test_importacao import _enviar
from .test_recuperacao import COMUM_CHEIO, _cliente, nfe_itens

COMERCIO = {"atividade": "comercio", "receita_bruta_anual": 1200000, "folha_clt_anual": 120000, "pro_labore_anual": 36000,
            "compras_anual": 720000, "despesas_creditaveis_anual": 60000}


def _planejar(c: TestClient, cid: int, dados: dict = COMERCIO) -> dict:
    r = c.post(f"/api/clientes/{cid}/simulacoes/completa", json=dados)
    assert r.status_code == 201, r.text
    return r.json()


def _notas(c: TestClient, cid: int, valores: list[float], inicio=(2025, 1)) -> None:
    arquivos = []
    for i, v in enumerate(valores):
        ano, mes = inicio[0] + (inicio[1] - 1 + i) // 12, (inicio[1] - 1 + i) % 12 + 1
        item = ("19059090", "5102", "102", "49", "", float(v), 0.0, "BISCOITO")
        arquivos.append((f"n{ano}{mes}.xml", nfe_itens(i + 1, f"{ano}-{mes:02d}-10", [item])))
    assert _enviar(c, cid, arquivos).json()["importados"] == len(valores)


def _planilha(c: TestClient, cid: int, linhas: list[str], cab="Mês;Receita;Compras;Folha;Pró-labore") -> None:
    csv = ("﻿" + "\n".join([cab, *linhas])).encode()
    mapa = {"competencia": 0, "receita": 1, "compras": 2, "folha": 3, "pro_labore": 4}
    r = c.post(f"/api/clientes/{cid}/financeiro/importar", files=[("arquivos", ("d.csv", csv))], data={"mapeamento": json.dumps(mapa)})
    assert r.status_code == 201, r.text


def _ac(c: TestClient, cid: int) -> dict:
    r = c.get(f"/api/clientes/{cid}/acompanhamento")
    assert r.status_code == 200, r.text
    return r.json()


def test_exige_login_e_isola_escritorios(logado: TestClient):
    cid = _cliente(logado)
    assert TestClient(logado.app).get(f"/api/clientes/{cid}/acompanhamento").status_code == 401
    cadastrar(logado, email="outra@escritorio.com.br", escritorio="Outro Escritório")
    assert logado.get(f"/api/clientes/{cid}/acompanhamento").status_code == 404


def test_sem_receita_realizada(logado: TestClient):
    cid = _cliente(logado)
    j = _ac(logado, cid)
    assert j["disponivel"] is False and "Importe" in j["motivo"]


def test_realizado_igual_ao_planejado_nao_muda_nada(logado: TestClient):
    cid = _cliente(logado)
    plano = _planejar(logado, cid)
    _planilha(logado, cid, [f"2025-{m:02d};100000,00;60000,00;10000,00;3000,00" for m in range(1, 13)])
    j = _ac(logado, cid)
    assert j["disponivel"] and j["meses"] == 12 and j["plano"]["simulacao_id"] == plano["id"]
    por = {x["campo"]: x for x in j["comparacao"]}
    assert por["receita"]["planejado"] == 1200000 and por["receita"]["realizado"] == 1200000 and por["receita"]["diferenca"] == 0
    assert por["compras"]["realizado"] == 720000 and por["folha"]["realizado"] == 120000 and por["pro_labore"]["realizado"] == 36000
    assert por["outras_despesas"]["realizado"] is None  # a planilha não trouxe
    assert j["desvio_receita"] == 0
    assert j["reavaliacao"]["mudou"] is False and j["reavaliacao"]["melhor_planejado"] == j["reavaliacao"]["melhor_realizado"]
    assert j["reavaliacao"]["totais_planejados"] == j["reavaliacao"]["totais_realizados"]
    assert j["resumo"][0].startswith("Receita dos últimos 12 meses, anualizada: R$ 1.200.000,00, 0% acima do planejado")


def test_receita_bem_acima_do_planejado_anualiza_e_reavalia(logado: TestClient):
    cid = _cliente(logado)
    _planejar(logado, cid)
    _planilha(logado, cid, [f"2025-{m:02d};150000,00;90000,00;10000,00;3000,00" for m in range(1, 7)])  # só 6 meses
    j = _ac(logado, cid)
    assert j["meses"] == 6
    por = {x["campo"]: x for x in j["comparacao"]}
    assert por["receita"]["realizado"] == 1800000 and por["receita"]["diferenca_pct"] == 0.5
    assert j["desvio_receita"] == 0.5
    assert j["reavaliacao"] is not None  # 6 meses bastam
    assert j["reavaliacao"]["totais_planejados"] != j["reavaliacao"]["totais_realizados"]


def test_menos_de_3_meses_nao_compara(logado: TestClient):
    cid = _cliente(logado)
    _planejar(logado, cid)
    _planilha(logado, cid, ["2025-01;100000,00;;;", "2025-02;100000,00;;;"])
    j = _ac(logado, cid)
    assert j["disponivel"] and j["plano"] is None and j["comparacao"] == [] and j["projecao"] is None


def test_entre_3_e_5_meses_compara_mas_nao_reavalia(logado: TestClient):
    cid = _cliente(logado)
    _planejar(logado, cid)
    _planilha(logado, cid, [f"2025-{m:02d};100000,00;;;" for m in range(1, 5)])
    j = _ac(logado, cid)
    assert j["plano"] and j["comparacao"] and j["reavaliacao"] is None


def test_sem_planejamento_so_projeta(logado: TestClient):
    cid = _cliente(logado)
    _planilha(logado, cid, [f"2025-{m:02d};{100000 + 1000 * m},00;;;" for m in range(1, 13)])
    j = _ac(logado, cid)
    assert j["plano"] is None and j["comparacao"] == [] and j["projecao"]["meses_base"] == 12


def test_planilha_tem_prioridade_sobre_as_notas_no_mesmo_mes(logado: TestClient):
    cid = _cliente(logado)
    _notas(logado, cid, [50000] * 6)
    _planilha(logado, cid, ["2025-01;80000,00;;;"])  # a contabilidade fechou o mês com mais receita que as notas
    j = _ac(logado, cid)
    assert j["realizado_anualizado"]["receita"] == round((80000 + 5 * 50000) / 6 * 12, 2)


def test_projecao_do_simples_cruzando_o_limite_e_aviso(logado: TestClient):
    cid = _cliente(logado)
    # RBT12 de 3,66 mi (76% do limite, já acima do sublimite): só a projeção alerta para o limite de 4,8 mi
    _planilha(logado, cid, [f"2025-{m:02d};{250000 + 10000 * (m - 1)},00;;;" for m in range(1, 13)])
    j = _ac(logado, cid)
    p = j["projecao"]
    assert p["confianca"] == "alta" and p["rbt12_atual"] == 12 * 250000 + 10000 * 66
    x = {c["codigo"]: c for c in p["cruzamentos"]}
    assert set(x) == {"simples_limite"} and x["simples_limite"]["limite"] == 4800000
    assert p["serie"][-1]["projetado"] is True and p["serie"][0]["projetado"] is False
    avisos = {a["codigo"]: a for a in logado.get("/api/avisos").json()["avisos"]}
    a = avisos["projecao_simples_limite"]
    assert a["titulo"].startswith("No ritmo atual, passa do limite do Simples em ")
    assert a["gravidade"] in ("atencao", "info") and a["acao"]["aba"] == "acompanhamento"


def test_projecao_so_enriquece_o_aviso_de_limite_que_ja_existe(logado: TestClient):
    cid = _cliente(logado)
    # RBT12 ~ 4,1 mi (85% do limite): o aviso de limite já existe e ganha a data prevista
    _planilha(logado, cid, [f"2025-{m:02d};{270000 + 14000 * (m - 1)},00;;;" for m in range(1, 13)])
    avisos = logado.get("/api/avisos").json()["avisos"]
    codigos = [a["codigo"] for a in avisos]
    assert "simples_limite" in codigos and "projecao_simples_limite" not in codigos
    texto = next(a for a in avisos if a["codigo"] == "simples_limite")["detalhe"]
    assert "No ritmo atual, passa do limite do Simples em " in texto


def test_projecao_de_baixa_confianca_nao_gera_aviso_proprio(logado: TestClient):
    cid = _cliente(logado)
    # 6 meses só, dispersos: confiança baixa
    _planilha(logado, cid, [f"2025-{m:02d};{v},00;;;" for m, v in zip(range(1, 7), (50000, 400000, 80000, 420000, 90000, 450000))])
    assert _ac(logado, cid)["projecao"]["confianca"] == "baixa"
    assert not any(a["codigo"].startswith("projecao_") for a in logado.get("/api/avisos").json()["avisos"])


def test_aviso_de_receita_fora_do_planejado(logado: TestClient):
    cid = _cliente(logado, status="ativo")
    _planejar(logado, cid, {**COMERCIO, "receita_bruta_anual": 600000, "compras_anual": 360000, "folha_clt_anual": 60000,
                           "pro_labore_anual": 24000, "despesas_creditaveis_anual": 20000})
    _planilha(logado, cid, [f"2025-{m:02d};100000,00;60000,00;5000,00;2000,00" for m in range(1, 13)])  # dobro do planejado
    a = next(a for a in logado.get("/api/avisos").json()["avisos"] if a["codigo"] == "planejado_desviado")
    assert a["gravidade"] in ("info", "atencao") and a["acao"]["aba"] == "acompanhamento"
    assert "Receita real" in a["titulo"] or "melhor opção passou" in a["titulo"]


def test_sem_aviso_quando_o_realizado_bate(logado: TestClient):
    cid = _cliente(logado)
    _planejar(logado, cid)
    _planilha(logado, cid, [f"2025-{m:02d};100000,00;60000,00;10000,00;3000,00" for m in range(1, 13)])
    assert not any(a["codigo"] == "planejado_desviado" for a in logado.get("/api/avisos").json()["avisos"])


def test_fator_r_com_a_folha_real(logado: TestClient):
    cid = _cliente(logado, atividade="servico_fator_r")
    _planejar(logado, cid, {"atividade": "servico_fator_r", "receita_bruta_anual": 600000, "folha_clt_anual": 96000, "pro_labore_anual": 60000})
    # folha real bem menor: o fator R despenca e o cliente cairia no Anexo V
    _planilha(logado, cid, [f"2025-{m:02d};50000,00;;1000,00;2000,00" for m in range(1, 13)])
    j = _ac(logado, cid)
    assert j["fator_r"] is not None and "Fator R" in j["fator_r"]["titulo"]
