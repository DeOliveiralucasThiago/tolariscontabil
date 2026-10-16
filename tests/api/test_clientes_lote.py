"""Importação de clientes em lote: prévia, análise, importação e complemento do cadastro pela consulta de CNPJ."""

from __future__ import annotations

import io
import json

import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook
from sqlalchemy import select

from tolaris_api import clientes_lote as lote
from tolaris_api.cnpj import CnpjIndisponivel, CnpjNaoEncontrado, DadosCnpj
from tolaris_api.db import get_db
from tolaris_api.models import Cliente
from tolaris_api.routers import clientes_lote as rota
from tolaris_api.routers.cnpj import get_consulta_cnpj

from .conftest import CNPJ_VALIDO, cadastrar

OUTRO = "11444777000161"
TERCEIRO = "45997418000153"


@pytest.fixture(autouse=True)
def sem_pausa(monkeypatch):
    monkeypatch.setattr(rota, "PAUSA_SEGUNDOS", 0)


def _csv(linhas: list[str], cab: str = "CNPJ;Razão social;Atividade;Regime;E-mail;Telefone") -> bytes:
    return ("﻿" + "\n".join([cab, *linhas])).encode("utf-8")


def _previa(c, conteudo, nome="c.csv"):
    return c.post("/api/clientes-lote/previa", files=[("arquivos", (nome, conteudo))])


def _enviar(c, caminho, conteudo, mapa, nome="c.csv", **campos):
    return c.post(f"/api/clientes-lote/{caminho}", files=[("arquivos", (nome, conteudo))],
                  data={"mapeamento": json.dumps(mapa), **campos})


MAPA = {"cnpj": 0, "razao_social": 1, "atividade": 2, "regime_atual": 3, "email": 4, "telefone": 5}


def _banco(c):
    return next(c.app.dependency_overrides[get_db]())


def test_normalizar_cnpj():
    assert lote.normalizar_cnpj("11.222.333/0001-81") == CNPJ_VALIDO
    assert lote.normalizar_cnpj("11222333000181") == CNPJ_VALIDO
    assert lote.normalizar_cnpj("1222333000181") is None  # 13 dígitos que, com um zero na frente, não fecham o dígito verificador
    assert lote.normalizar_cnpj("11222333000182") is None
    assert lote.normalizar_cnpj("123") is None
    assert lote.normalizar_cnpj("") is None
    assert lote.normalizar_cnpj("4252011000110") == "04252011000110"  # o Excel tira o zero à esquerda


def test_exige_login_e_baixa_modelo(logado: TestClient):
    r = logado.get("/api/clientes-lote/modelo.csv")
    assert r.status_code == 200 and r.content.startswith(b"\xef\xbb\xbf") and b"CNPJ" in r.content
    anonimo = TestClient(logado.app)
    assert anonimo.post("/api/clientes-lote/previa").status_code == 401
    assert anonimo.get("/api/clientes-lote/pendentes").status_code == 401
    assert anonimo.post("/api/clientes-lote/completar").status_code == 401


def test_previa_sugere_colunas(logado: TestClient):
    r = _previa(logado, _csv([f"{CNPJ_VALIDO};Padaria;Comércio;Simples;a@b.com;11999990000"]))
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["total_linhas"] == 1
    assert j["sugestao"]["cnpj"] == 0 and j["sugestao"]["razao_social"] == 1 and j["sugestao"]["atividade"] == 2
    assert j["sugestao"]["regime_atual"] == 3 and j["sugestao"]["email"] == 4 and j["sugestao"]["telefone"] == 5
    assert j["sugestao"]["observacoes"] is None


def test_analise_classifica_sem_gravar(logado: TestClient):
    logado.post("/api/clientes", json={"razao_social": "Já existe Ltda", "cnpj": CNPJ_VALIDO})
    linhas = [
        f"{CNPJ_VALIDO};Já existe;;;;",       # existente
        f"{OUTRO};Novo A;;;;",                # novo
        f"{OUTRO};Novo A de novo;;;;",        # repetido
        "11222333000199;Inválido;;;;",         # dígito verificador
        f"{TERCEIRO};;;;;",                    # novo, só CNPJ
        ";linha sem cnpj;;;;",                 # ignorada em silêncio
    ]
    r = _enviar(logado, "analisar", _csv(linhas), MAPA)
    assert r.status_code == 200, r.text
    j = r.json()
    assert (j["novos"], j["existentes"], j["repetidos"], j["invalidos"]) == (2, 1, 1, 1)
    assert j["total_problemas"] == 3
    assert {p["linha"]: p["situacao"] for p in j["problemas"]} == {2: "existente", 4: "repetido", 5: "invalido"}
    assert len(logado.get("/api/clientes").json()) == 1  # nada foi gravado


def test_importa_so_com_cnpj_e_marca_pendentes(logado: TestClient):
    linhas = [f"{CNPJ_VALIDO};Padaria Pão Bom;Comércio;Simples Nacional;CONTATO@Padaria.com;(11) 98765-4321", f"{OUTRO};;;;;"]
    r = _enviar(logado, "importar", _csv(linhas), MAPA)
    assert r.status_code == 201, r.text
    j = r.json()
    assert j["criados"] == 2 and j["pendentes"] == 1
    clientes = {c["cnpj"]: c for c in logado.get("/api/clientes").json()}
    a, b = clientes[CNPJ_VALIDO], clientes[OUTRO]
    assert (a["razao_social"], a["atividade"], a["regime_atual"], a["status"]) == ("Padaria Pão Bom", "comercio", "simples", "ativo")
    assert a["email"] == "contato@padaria.com" and a["telefone"] == "(11) 98765-4321" and a["cadastro_pendente"] is False
    assert b["razao_social"] == "CNPJ 11.444.777/0001-61" and b["cadastro_pendente"] is True
    assert logado.get("/api/clientes-lote/pendentes").json() == {"pendentes": 1}


def test_status_padrao_e_status_da_planilha(logado: TestClient):
    mapa = {"cnpj": 0, "razao_social": 1, "status": 2}
    csv = _csv([f"{CNPJ_VALIDO};A Ltda;inativo", f"{OUTRO};B Ltda;"], cab="CNPJ;Razão social;Situação")
    assert _enviar(logado, "importar", csv, mapa, status_padrao="prospect").status_code == 201
    por = {c["cnpj"]: c["status"] for c in logado.get("/api/clientes").json()}
    assert por == {CNPJ_VALIDO: "inativo", OUTRO: "prospect"}
    assert _enviar(logado, "importar", csv, mapa, status_padrao="qualquer").status_code == 422


def test_valores_nao_reconhecidos_viram_aviso(logado: TestClient):
    csv = _csv([f"{CNPJ_VALIDO};A Ltda;Padaria;Regime estranho;nao-e-email;"])
    j = _enviar(logado, "analisar", csv, MAPA).json()
    assert len(j["avisos"]) == 3 and any("Padaria" in a for a in j["avisos"])
    assert _enviar(logado, "importar", csv, MAPA).status_code == 201
    c = logado.get("/api/clientes").json()[0]
    assert c["atividade"] is None and c["regime_atual"] is None and c["email"] is None and c["cadastro_pendente"] is True


def test_xlsx_com_cnpj_numerico_sem_zero_a_esquerda(logado: TestClient):
    cnpj_com_zero = "04252011000110"  # CNPJ real válido que começa com zero
    assert lote.normalizar_cnpj(cnpj_com_zero) == cnpj_com_zero
    wb = Workbook()
    ws = wb.active
    ws.append(["CNPJ", "Razão social"])
    ws.append([int(cnpj_com_zero), "Empresa Zero Ltda"])  # o Excel guarda 4252011000110
    ws.append([int(CNPJ_VALIDO), "Padaria Ltda"])
    buf = io.BytesIO()
    wb.save(buf)
    r = _enviar(logado, "importar", buf.getvalue(), {"cnpj": 0, "razao_social": 1}, nome="c.xlsx")
    assert r.status_code == 201, r.text
    assert {c["cnpj"] for c in logado.get("/api/clientes").json()} == {cnpj_com_zero, CNPJ_VALIDO}


def test_erros_claros(logado: TestClient):
    ok = _csv([f"{CNPJ_VALIDO};A;;;;"])
    assert _enviar(logado, "importar", ok, {"razao_social": 1}).status_code == 400  # sem coluna de CNPJ
    assert _enviar(logado, "importar", ok, {"cnpj": 9}).status_code == 400
    assert _enviar(logado, "importar", ok, {"cnpj": 0, "razao_social": 0}).status_code == 400
    assert _enviar(logado, "importar", ok, {"cnpj": True}).status_code == 400
    assert logado.post("/api/clientes-lote/importar", files=[("arquivos", ("c.csv", ok))], data={"mapeamento": "xx"}).status_code == 400
    r = _enviar(logado, "importar", _csv(["abc;;;;;"]), MAPA)
    assert r.status_code == 400 and "Nenhum cliente novo" in r.json()["detail"]
    assert _enviar(logado, "importar", b"%PDF", MAPA, nome="c.pdf").status_code == 400
    duas = logado.post("/api/clientes-lote/previa", files=[("arquivos", ("a.csv", ok)), ("arquivos", ("b.csv", ok))])
    assert duas.status_code == 400


def test_reimportar_nao_duplica(logado: TestClient):
    csv = _csv([f"{CNPJ_VALIDO};A;;;;"])
    assert _enviar(logado, "importar", csv, MAPA).status_code == 201
    r = _enviar(logado, "importar", csv, MAPA)
    assert r.status_code == 400 and len(logado.get("/api/clientes").json()) == 1


def test_mesmo_cnpj_em_outro_escritorio_nao_conta_como_existente(logado: TestClient):
    csv = _csv([f"{CNPJ_VALIDO};A;;;;"])
    assert _enviar(logado, "importar", csv, MAPA).status_code == 201
    cadastrar(logado, email="outra@escritorio.com.br", escritorio="Outro Escritório")
    assert _enviar(logado, "importar", csv, MAPA).status_code == 201
    assert len(logado.get("/api/clientes").json()) == 1  # só o do escritório logado


# --- Completar pelo CNPJ ---------------------------------------------------------------------------------
def _dados(cnpj: str, razao: str = "ACME CONSULTORIA LTDA") -> DadosCnpj:
    return DadosCnpj(
        cnpj=cnpj, razao_social=razao, nome_fantasia="ACME", situacao="ATIVA", cnae_principal="7020400",
        cnae_descricao="Consultoria em gestão", municipio="SAO PAULO", uf="SP", email="contato@acme.com.br",
        telefone="1133334444", opcao_simples=True, opcao_mei=False)


def test_completar_preenche_so_o_que_esta_vazio(logado: TestClient):
    csv = _csv([f"{CNPJ_VALIDO};;;;meu@email.com.br;", f"{OUTRO};Nome que eu digitei;;;;"])
    _enviar(logado, "importar", csv, MAPA)
    logado.app.dependency_overrides[get_consulta_cnpj] = lambda: _dados
    r = logado.post("/api/clientes-lote/completar")
    assert r.status_code == 200, r.text
    assert r.json() == {"completados": 2, "nao_encontrados": [], "restantes": 0, "indisponivel": False}
    por = {c["cnpj"]: c for c in logado.get("/api/clientes").json()}
    a, b = por[CNPJ_VALIDO], por[OUTRO]
    assert a["razao_social"] == "ACME CONSULTORIA LTDA" and a["email"] == "meu@email.com.br"  # e-mail digitado fica
    assert a["atividade"] == "servico_fator_r" and a["regime_atual"] == "simples" and a["uf"] == "SP" and a["cnae_principal"] == "7020400"
    assert b["razao_social"] == "Nome que eu digitei"  # nome digitado nunca é trocado
    assert b["atividade"] == "servico_fator_r" and a["cadastro_pendente"] is False and b["cadastro_pendente"] is False


def _cnpj_com_dv(base12: str) -> str:
    def dv(d: str) -> str:
        pesos = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2][-len(d):]
        r = sum(int(x) * p for x, p in zip(d, pesos)) % 11
        return str(0 if r < 2 else 11 - r)
    d1 = dv(base12)
    return base12 + d1 + dv(base12 + d1)


def test_completar_em_lotes_de_15(logado: TestClient):
    cnpjs = [_cnpj_com_dv(f"{20000000 + i:08d}0001") for i in range(20)]
    assert all(lote.normalizar_cnpj(c) == c for c in cnpjs)
    _enviar(logado, "importar", _csv([f"{c};;;;;" for c in cnpjs]), MAPA)
    logado.app.dependency_overrides[get_consulta_cnpj] = lambda: _dados
    assert logado.get("/api/clientes-lote/pendentes").json() == {"pendentes": 20}
    r1 = logado.post("/api/clientes-lote/completar").json()
    assert r1["completados"] == 15 and r1["restantes"] == 5
    r2 = logado.post("/api/clientes-lote/completar").json()
    assert r2["completados"] == 5 and r2["restantes"] == 0


def test_completar_nao_encontrado_e_indisponivel(logado: TestClient):
    _enviar(logado, "importar", _csv([f"{CNPJ_VALIDO};;;;;", f"{OUTRO};;;;;", f"{TERCEIRO};;;;;"]), MAPA)

    def consulta(cnpj):
        if cnpj == CNPJ_VALIDO:
            raise CnpjNaoEncontrado(cnpj)
        if cnpj == TERCEIRO:
            raise CnpjIndisponivel("fora do ar")
        return _dados(cnpj)

    logado.app.dependency_overrides[get_consulta_cnpj] = lambda: consulta
    j = logado.post("/api/clientes-lote/completar").json()
    assert j["completados"] == 1 and j["indisponivel"] is True and j["restantes"] == 1
    assert j["nao_encontrados"] == [{"cnpj": "11.222.333/0001-81", "motivo": "Não encontrado na Receita Federal"}]
    por = {c["cnpj"]: c for c in logado.get("/api/clientes").json()}
    assert por[CNPJ_VALIDO]["razao_social"].startswith("CNPJ ") and por[CNPJ_VALIDO]["cadastro_pendente"] is False
    assert por[TERCEIRO]["cadastro_pendente"] is True  # fica para a próxima tentativa


def test_completar_so_toca_nos_clientes_do_proprio_escritorio(logado: TestClient):
    _enviar(logado, "importar", _csv([f"{CNPJ_VALIDO};;;;;"]), MAPA)
    cadastrar(logado, email="outra@escritorio.com.br", escritorio="Outro Escritório")
    logado.app.dependency_overrides[get_consulta_cnpj] = lambda: _dados
    assert logado.get("/api/clientes-lote/pendentes").json() == {"pendentes": 0}
    assert logado.post("/api/clientes-lote/completar").json()["completados"] == 0
    db = _banco(logado)
    try:
        assert db.scalar(select(Cliente).where(Cliente.cnpj == CNPJ_VALIDO)).cadastro_pendente is True
    finally:
        db.close()


def test_limite_de_clientes_por_planilha(logado: TestClient, monkeypatch):
    monkeypatch.setattr(lote, "LIMITE_CLIENTES", 2)
    csv = _csv([f"{CNPJ_VALIDO};;;;;", f"{OUTRO};;;;;", f"{TERCEIRO};;;;;"])
    r = _enviar(logado, "analisar", csv, MAPA)
    assert r.status_code == 400 and "divida" in r.json()["detail"]
