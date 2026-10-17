"""Funil comercial: etapas, conversões, valores, uma proposta por cliente e ações sugeridas."""

from __future__ import annotations

from datetime import timedelta
from itertools import count

from fastapi.testclient import TestClient
from sqlalchemy import select

from tolaris_api.acesso import agora
from tolaris_api.db import get_db
from tolaris_api.models import Envio, Simulacao

from .conftest import cadastrar

COMPLETA = {"atividade": "comercio", "receita_bruta_anual": 1200000, "folha_clt_anual": 120000, "pro_labore_anual": 36000,
            "compras_anual": 720000, "despesas_creditaveis_anual": 60000}
_contador = count(1)


def _cnpj() -> str:
    """CNPJ válido novo a cada chamada (base de 8 dígitos sequencial + filial 0001 + dígitos verificadores)."""
    base = f"{30000000 + next(_contador):08d}0001"

    def dv(d: str) -> str:
        pesos = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2][-len(d):]
        r = sum(int(x) * p for x, p in zip(d, pesos)) % 11
        return str(0 if r < 2 else 11 - r)

    d1 = dv(base)
    return base + d1 + dv(base + d1)


def _proposta(c: TestClient, nome: str, mensal: float, adesao: float = 0, validade: int = 15) -> tuple[int, int]:
    cid = c.post("/api/clientes", json={"razao_social": nome, "cnpj": _cnpj()}).json()["id"]
    sim = c.post(f"/api/clientes/{cid}/simulacoes/completa", json=COMPLETA).json()
    r = c.put(f"/api/simulacoes/{sim['id']}/honorarios", json={"valor_mensal": mensal, "adesao": adesao, "validade_dias": validade})
    assert r.status_code == 200, r.text
    return cid, sim["id"]


def _publicar(c: TestClient, sid: int) -> None:
    assert c.patch(f"/api/simulacoes/{sid}/publicacao", json={"publicada": True}).status_code == 200


def _portal(c: TestClient, cid: int) -> str:
    return c.post(f"/api/clientes/{cid}/portal", json={}).json()["link"].rsplit("/", 1)[1]


def _ajustar(c: TestClient, sid: int, **campos) -> None:
    """Mexe nos instantes direto no banco (para simular dias passados)."""
    db = next(c.app.dependency_overrides[get_db]())
    try:
        s = db.get(Simulacao, sid)
        for k, v in campos.items():
            if k.startswith("hon_"):
                s.honorarios = {**s.honorarios, k[4:]: v}
            else:
                setattr(s, k, v)
        db.commit()
    finally:
        db.close()


def _funil(c: TestClient, **params) -> dict:
    r = c.get("/api/funil", params=params)
    assert r.status_code == 200, r.text
    return r.json()


def _quantidades(j: dict) -> list[int]:
    return [e["quantidade"] for e in j["funil"]]


def test_exige_login_e_comeca_vazio(logado: TestClient):
    assert TestClient(logado.app).get("/api/funil").status_code == 401
    j = _funil(logado)
    assert _quantidades(j) == [0, 0, 0, 0] and j["propostas"] == [] and j["resumo"]["taxa_aceite"] is None
    assert [e["etapa"] for e in j["funil"]] == ["criada", "enviada", "vista", "aceita"]


def test_cada_etapa_e_os_valores(logado: TestClient):
    _, nao_enviada = _proposta(logado, "Cliente Criada", 500)
    _, publicada = _proposta(logado, "Cliente Enviada", 800)
    _publicar(logado, publicada)
    cid_vista, vista = _proposta(logado, "Cliente Vista", 1000)
    _publicar(logado, vista)
    token_v = _portal(logado, cid_vista)
    TestClient(logado.app).post(f"/api/portal/{token_v}/simulacoes/{vista}/visto")
    cid_ac, aceita = _proposta(logado, "Cliente Aceita", 1500, adesao=300)
    _publicar(logado, aceita)
    token_a = _portal(logado, cid_ac)
    anonimo = TestClient(logado.app)
    anonimo.post(f"/api/portal/{token_a}/simulacoes/{aceita}/visto")
    assert anonimo.post(f"/api/portal/{token_a}/simulacoes/{aceita}/aceite", json={"nome": "Maria", "confirmo": True}).status_code == 200

    j = _funil(logado)
    assert _quantidades(j) == [4, 3, 2, 1]
    assert [e["valor_mensal"] for e in j["funil"]] == [3800, 3300, 2500, 1500]
    assert [e["conversao"] for e in j["funil"]] == [None, 0.75, 0.6667, 0.5]
    etapas = {p["cliente"]: p["etapa"] for p in j["propostas"]}
    assert etapas == {"Cliente Criada": "criada", "Cliente Enviada": "enviada", "Cliente Vista": "vista", "Cliente Aceita": "aceita"}
    r = j["resumo"]
    assert (r["aceitas_valor_mensal"], r["aceitas_adesao"], r["aceitas_primeiro_ano"]) == (1500, 300, 18300)
    assert (r["em_aberto"], r["em_aberto_valor_mensal"], r["taxa_aceite"]) == (3, 2300, round(1 / 3, 4))
    assert r["economia_anual_aceitas"] > 0
    # ordem: o que está vista primeiro, depois enviada, criada, aceita
    assert [p["etapa"] for p in j["propostas"]] == ["vista", "enviada", "criada", "aceita"]


def test_envio_por_email_conta_como_enviada(logado: TestClient):
    _, sid = _proposta(logado, "Cliente Email", 700)
    assert _funil(logado)["funil"][1]["quantidade"] == 0
    r = logado.post(f"/api/simulacoes/{sid}/enviar", json={"para": ["dono@cliente.com.br"]})
    assert r.status_code == 201
    j = _funil(logado)
    assert _quantidades(j) == [1, 1, 0, 0] and j["propostas"][0]["etapa"] == "enviada"
    db = next(logado.app.dependency_overrides[get_db]())
    try:
        assert db.scalar(select(Envio).where(Envio.simulacao_id == sid)).status == "enviado"
    finally:
        db.close()


def test_envio_que_falhou_nao_conta(logado: TestClient, monkeypatch):
    from tolaris_api.routers import compartilhamento
    from tolaris_api.emails import ErroEnvio

    def falha(*a, **k):
        raise ErroEnvio("fora do ar")
    monkeypatch.setattr(compartilhamento, "enviar", falha)
    _, sid = _proposta(logado, "Cliente Falha", 700)
    assert logado.post(f"/api/simulacoes/{sid}/enviar", json={"para": ["a@b.com.br"]}).status_code == 502
    assert _quantidades(_funil(logado)) == [1, 0, 0, 0]


def test_uma_proposta_por_cliente_a_mais_recente(logado: TestClient):
    cid, antiga = _proposta(logado, "Cliente Refeito", 500)
    _publicar(logado, antiga)
    nova = logado.post(f"/api/clientes/{cid}/simulacoes/completa", json=COMPLETA).json()["id"]
    logado.put(f"/api/simulacoes/{nova}/honorarios", json={"valor_mensal": 900})
    j = _funil(logado)
    assert j["resumo"]["propostas"] == 1 and j["propostas"][0]["simulacao_id"] == nova and j["propostas"][0]["valor_mensal"] == 900
    assert _quantidades(j) == [1, 0, 0, 0]  # a nova ainda não foi enviada


def test_proposta_vencida_sem_aceite_e_fora_do_em_aberto(logado: TestClient):
    cid, sid = _proposta(logado, "Cliente Vencida", 600)
    _publicar(logado, sid)
    ontem = (agora() - timedelta(days=1)).date().isoformat()
    _ajustar(logado, sid, hon_valido_ate=ontem)
    j = _funil(logado)
    assert j["propostas"][0]["etapa"] == "vencida" and j["resumo"]["vencidas"] == 1 and j["resumo"]["vencidas_valor_mensal"] == 600
    assert j["resumo"]["em_aberto"] == 0
    assert _quantidades(j) == [1, 1, 0, 0]  # chegou a ser enviada; a etapa conta o caminho percorrido
    assert "Venceu sem aceite" in j["propostas"][0]["acao"]


def test_aceite_depois_do_vencimento_continua_aceita(logado: TestClient):
    cid, sid = _proposta(logado, "Cliente Aceitou", 600)
    _publicar(logado, sid)
    _ajustar(logado, sid, aceite_em=agora() - timedelta(days=5), aceite_nome="Maria", hon_valido_ate=(agora() - timedelta(days=2)).date().isoformat())
    assert _funil(logado)["propostas"][0]["etapa"] == "aceita"


def test_acoes_sugeridas_e_dias_parados(logado: TestClient):
    cid1, nunca = _proposta(logado, "Cliente Nunca Enviada", 500)
    cid2, parada = _proposta(logado, "Cliente Nao Abriu", 700)
    _publicar(logado, parada)
    _ajustar(logado, parada, publicada_em=agora() - timedelta(days=5), hon_definido_em=(agora() - timedelta(days=6)).isoformat())
    cid3, vista = _proposta(logado, "Cliente Calado", 900)
    _publicar(logado, vista)
    _ajustar(logado, vista, publicada_em=agora() - timedelta(days=12), visto_primeira_em=agora() - timedelta(days=9),
             hon_definido_em=(agora() - timedelta(days=13)).isoformat())
    cid4, vence = _proposta(logado, "Cliente Quase Vencendo", 400, validade=2)
    _publicar(logado, vence)
    por = {p["cliente"]: p for p in _funil(logado)["propostas"]}
    assert "Publique no portal" in por["Cliente Nunca Enviada"]["acao"]
    assert "5 dias e ainda não aberta" in por["Cliente Nao Abriu"]["acao"] and por["Cliente Nao Abriu"]["dias_parada"] == 5
    assert "Vista há 9 dias sem resposta" in por["Cliente Calado"]["acao"] and por["Cliente Calado"]["dias_parada"] == 9
    assert "Vence em 2 dias" in por["Cliente Quase Vencendo"]["acao"]
    assert _funil(logado)["precisam_de_acao"] == 4


def test_sem_acao_quando_esta_no_prazo(logado: TestClient):
    cid, sid = _proposta(logado, "Cliente Recente", 500)
    _publicar(logado, sid)
    p = _funil(logado)["propostas"][0]
    assert p["acao"] is None and p["dias_parada"] == 0


def test_tempos_medios_ate_visto_e_aceite(logado: TestClient):
    agora_ = agora()
    for nome, vis, ace in (("Um", 2, 4), ("Dois", 4, 10)):
        cid, sid = _proposta(logado, f"Cliente {nome}", 500)
        _publicar(logado, sid)
        _ajustar(logado, sid, publicada_em=agora_ - timedelta(days=12), visto_primeira_em=agora_ - timedelta(days=12 - vis),
                 aceite_em=agora_ - timedelta(days=12 - ace), aceite_nome="X")
    r = _funil(logado)["resumo"]
    assert r["dias_ate_visto"] == 3.0 and r["dias_ate_aceite"] == 7.0 and r["taxa_aceite"] == 1.0


def test_periodo_filtra_pela_data_da_proposta(logado: TestClient):
    _, nova = _proposta(logado, "Cliente Recente", 500)
    _, velha = _proposta(logado, "Cliente Antigo", 800)
    _ajustar(logado, velha, hon_definido_em=(agora() - timedelta(days=200)).isoformat())
    assert _funil(logado, dias=30)["resumo"]["propostas"] == 1
    assert _funil(logado, dias=90)["resumo"]["propostas"] == 1
    assert _funil(logado, dias=365)["resumo"]["propostas"] == 2
    assert _funil(logado, dias=0)["resumo"]["propostas"] == 2
    assert logado.get("/api/funil", params={"dias": -1}).status_code == 422


def test_simulacao_sem_proposta_e_outro_escritorio_ficam_de_fora(logado: TestClient):
    cid = logado.post("/api/clientes", json={"razao_social": "Sem Proposta"}).json()["id"]
    logado.post(f"/api/clientes/{cid}/simulacoes/completa", json=COMPLETA)
    _proposta(logado, "Cliente Com Proposta", 500)
    assert _funil(logado)["resumo"]["propostas"] == 1
    cadastrar(logado, email="outra@escritorio.com.br", escritorio="Outro Escritório")
    assert _funil(logado)["resumo"]["propostas"] == 0
