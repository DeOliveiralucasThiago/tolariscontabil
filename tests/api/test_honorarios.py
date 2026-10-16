from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from io import BytesIO

from fastapi.testclient import TestClient
from pypdf import PdfReader

from tolaris_api.db import get_db
from tolaris_api.models import Simulacao

from .conftest import cadastrar
from .test_avisos import COMERCIO, _avisos, _planejar
from .test_recuperacao import _cliente

TABELA = {"base": {"mei": 150, "simples": 800, "presumido": 1500, "real": 3000}, "por_funcionario": 70, "adesao": 500,
          "servicos": "Escrituração fiscal e contábil\nFolha de pagamento\nPlanejamento tributário anual", "validade_dias": 15}
PROPOSTA = {"funcionarios": 3}


@contextmanager
def banco(c: TestClient):
    """Sessão direta no banco do teste, para ajustar datas que a API não permite alterar."""
    db = next(c.app.dependency_overrides[get_db]())
    try:
        yield db
    finally:
        db.close()


def _cenario(c: TestClient, **cliente) -> tuple[int, dict]:
    """Cliente do comércio com planejamento (recomenda o Simples) e tabela de honorários do escritório."""
    assert c.patch("/api/escritorio", json={"honorarios": TABELA}).status_code == 200
    cid = _cliente(c, **cliente)
    return cid, _planejar(c, cid, COMERCIO)


def _publicar_e_gerar_link(c: TestClient, cid: int, sim_id: int) -> str:
    assert c.patch(f"/api/simulacoes/{sim_id}/publicacao", json={"publicada": True}).status_code == 200
    link = c.post(f"/api/clientes/{cid}/portal", json={}).json()["link"]
    return link.rsplit("/", 1)[1]


def test_tabela_de_honorarios_do_escritorio(logado: TestClient):
    r = logado.patch("/api/escritorio", json={"honorarios": TABELA})
    assert r.status_code == 200
    h = r.json()["escritorio"]["honorarios"]
    assert h["base"] == {"mei": 150.0, "simples": 800.0, "presumido": 1500.0, "real": 3000.0}
    assert h["por_funcionario"] == 70.0 and h["adesao"] == 500.0 and h["validade_dias"] == 15
    assert logado.get("/api/auth/me").json()["escritorio"]["honorarios"]["base"]["simples"] == 800.0
    assert logado.patch("/api/escritorio", json={"honorarios": {"base": {"simples": -1}}}).status_code == 422
    assert logado.patch("/api/escritorio", json={"honorarios": {"base": {"outro": 10}}}).status_code == 422
    assert logado.patch("/api/escritorio", json={"honorarios": {"validade_dias": 0}}).status_code == 422


def test_sugestao_pelo_regime_recomendado_e_funcionarios(logado: TestClient):
    cid, sim = _cenario(logado)
    assert sim["resultado"]["melhor"] == "Simples Nacional"
    s = logado.get(f"/api/simulacoes/{sim['id']}/honorarios/sugestao?funcionarios=3").json()
    assert s["regime"] == "simples" and s["base"] == 800 and s["por_funcionario"] == 70
    assert s["valor_mensal"] == 1010 and s["adesao"] == 500 and s["configurado"] is True
    assert "Folha de pagamento" in s["servicos"]
    # Sem tabela, a sugestão vem zerada
    logado.patch("/api/escritorio", json={"honorarios": {}})
    assert logado.get(f"/api/simulacoes/{sim['id']}/honorarios/sugestao").json()["valor_mensal"] == 0


def test_definir_proposta_com_valores_da_tabela_ou_informados(logado: TestClient):
    cid, sim = _cenario(logado)
    r = logado.put(f"/api/simulacoes/{sim['id']}/honorarios", json=PROPOSTA)
    assert r.status_code == 200, r.text
    h = r.json()["honorarios"]
    assert h["valor_mensal"] == 1010 and h["adesao"] == 500 and h["funcionarios"] == 3 and h["validade_dias"] == 15
    esperado = (datetime.now(timezone.utc) + timedelta(days=15)).date()
    assert abs((datetime.fromisoformat(h["valido_ate"]).date() - esperado).days) <= 1   # fuso de São Paulo
    # Valores informados valem mais que a tabela
    h2 = logado.put(f"/api/simulacoes/{sim['id']}/honorarios", json={
        "valor_mensal": 1200, "adesao": 0, "servicos": "Só contabilidade", "validade_dias": 30}).json()["honorarios"]
    assert (h2["valor_mensal"], h2["adesao"], h2["servicos"], h2["validade_dias"]) == (1200, 0, "Só contabilidade", 30)
    assert logado.delete(f"/api/simulacoes/{sim['id']}/honorarios").status_code == 204
    assert logado.get(f"/api/clientes/{cid}/simulacoes").json()[0]["honorarios"] is None


def test_proposta_sem_valor_e_recusada(logado: TestClient):
    cid = _cliente(logado)
    sim = _planejar(logado, cid, COMERCIO)
    r = logado.put(f"/api/simulacoes/{sim['id']}/honorarios", json={})
    assert r.status_code == 422 and "tabela de honorários" in r.json()["detail"]
    assert logado.put(f"/api/simulacoes/{sim['id']}/honorarios", json={"valor_mensal": -5}).status_code == 422


def _texto_pdf(c: TestClient, sim_id: int) -> str:
    pdf = c.get(f"/api/simulacoes/{sim_id}/proposta.pdf")
    assert pdf.status_code == 200
    return "\n".join(p.extract_text() or "" for p in PdfReader(BytesIO(pdf.content)).pages)


def test_pdf_traz_a_proposta_de_honorarios(logado: TestClient):
    cid, sim = _cenario(logado)
    assert "Proposta de honorários" not in _texto_pdf(logado, sim["id"])
    logado.put(f"/api/simulacoes/{sim['id']}/honorarios", json=PROPOSTA)
    texto = _texto_pdf(logado, sim["id"])
    assert "Proposta de honorários" in texto and "R$ 1.010,00" in texto and "R$ 500,00" in texto
    assert "R$ 12.620,00" in texto                       # 12 x 1.010 + adesão de 500
    assert "Escrituração fiscal e contábil" in texto and "Proposta válida até" in texto
    economia = sim["resultado"]["economia_vs_pior"]
    assert f"{economia:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") in texto
    assert "cerca de 8,1 vezes os honorários" in texto      # 102.723,60 / 12.620,00 (a linha quebra antes de "primeiro ano")


def test_publicar_registra_a_data(logado: TestClient):
    cid, sim = _cenario(logado)
    r = logado.patch(f"/api/simulacoes/{sim['id']}/publicacao", json={"publicada": True}).json()
    assert r["publicada"] and r["publicada_em"] is not None
    assert logado.patch(f"/api/simulacoes/{sim['id']}/publicacao", json={"publicada": False}).json()["publicada_em"] is None


def test_confirmacao_de_leitura_no_portal(logado: TestClient):
    cid, sim = _cenario(logado)
    token = _publicar_e_gerar_link(logado, cid, sim["id"])
    visto = f"/api/portal/{token}/simulacoes/{sim['id']}/visto"
    inicial = logado.get(f"/api/clientes/{cid}/simulacoes").json()[0]
    assert inicial["aberturas"] == 0 and inicial["visto_primeira_em"] is None
    assert logado.post(visto).status_code == 204
    s = logado.get(f"/api/clientes/{cid}/simulacoes").json()[0]
    assert s["aberturas"] == 1 and s["visto_primeira_em"] is not None
    # Recarregar a página logo em seguida e baixar o PDF contam como a mesma abertura
    logado.post(visto)
    assert logado.get(f"/api/portal/{token}/simulacoes/{sim['id']}.pdf").status_code == 200
    assert logado.get(f"/api/clientes/{cid}/simulacoes").json()[0]["aberturas"] == 1
    # Depois de 10 minutos, é uma nova abertura
    with banco(logado) as db:
        s_db = db.get(Simulacao, sim["id"])
        s_db.visto_ultima_em = datetime.now(timezone.utc) - timedelta(minutes=11)
        db.commit()
    logado.post(visto)
    assert logado.get(f"/api/clientes/{cid}/simulacoes").json()[0]["aberturas"] == 2


def test_leitura_so_de_relatorio_publicado_do_proprio_cliente(logado: TestClient):
    cid, sim = _cenario(logado)
    token = _publicar_e_gerar_link(logado, cid, sim["id"])
    outro = _cliente(logado, cnpj="45997418000153")
    nao_publicada = _planejar(logado, outro, COMERCIO)
    assert logado.post(f"/api/portal/{token}/simulacoes/{nao_publicada['id']}/visto").status_code == 404
    assert logado.post(f"/api/portal/{token}/simulacoes/999/visto").status_code == 404
    assert logado.post(f"/api/portal/token-invalido/simulacoes/{sim['id']}/visto").status_code == 404


def test_portal_mostra_a_proposta_e_o_aceite(logado: TestClient):
    cid, sim = _cenario(logado)
    logado.put(f"/api/simulacoes/{sim['id']}/honorarios", json=PROPOSTA)
    token = _publicar_e_gerar_link(logado, cid, sim["id"])
    p = logado.get(f"/api/portal/{token}").json()["simulacoes"][0]
    assert p["honorarios"]["valor_mensal"] == 1010 and p["honorarios"]["expirada"] is False and p["aceite_em"] is None
    assert "definido_em" not in p["honorarios"] and "funcionarios" not in p["honorarios"]

    r = logado.post(f"/api/portal/{token}/simulacoes/{sim['id']}/aceite", json={"nome": "  João   da Silva ", "confirmo": True})
    assert r.status_code == 200, r.text
    assert r.json()["aceite_nome"] == "João da Silva"
    p = logado.get(f"/api/portal/{token}").json()["simulacoes"][0]
    assert p["aceite_nome"] == "João da Silva" and p["aceite_em"] is not None
    assert "Aceite eletrônico" in _texto_pdf(logado, sim["id"])


def test_aceite_avisa_o_escritorio_por_email(logado: TestClient, caixa_limpa):
    cid, sim = _cenario(logado)
    logado.put(f"/api/simulacoes/{sim['id']}/honorarios", json=PROPOSTA)
    token = _publicar_e_gerar_link(logado, cid, sim["id"])
    logado.post(f"/api/portal/{token}/simulacoes/{sim['id']}/aceite", json={"nome": "João da Silva", "confirmo": True})
    aviso = [m for m in caixa_limpa if m.assunto.startswith("Proposta aceita")]
    assert len(aviso) == 1 and aviso[0].para == ["ana@escritorio.com.br"]
    assert "João da Silva" in aviso[0].texto and "R$ 1.010,00" in aviso[0].texto and "adesão de R$ 500,00" in aviso[0].texto
    assert "Mercadinho Boa Compra" in aviso[0].assunto


def test_aceite_regras(logado: TestClient):
    cid, sim = _cenario(logado)
    token = _publicar_e_gerar_link(logado, cid, sim["id"])
    aceite = f"/api/portal/{token}/simulacoes/{sim['id']}/aceite"
    corpo = {"nome": "João da Silva", "confirmo": True}
    assert logado.post(aceite, json=corpo).status_code == 404            # relatório sem proposta de honorários
    logado.put(f"/api/simulacoes/{sim['id']}/honorarios", json=PROPOSTA)
    assert logado.post(aceite, json={"nome": "João da Silva", "confirmo": False}).status_code == 422
    assert logado.post(aceite, json={"nome": "Jo", "confirmo": True}).status_code == 422
    assert logado.post(f"/api/portal/token-invalido/simulacoes/{sim['id']}/aceite", json=corpo).status_code == 404
    # Proposta vencida
    with banco(logado) as db:
        s = db.get(Simulacao, sim["id"])
        h = dict(s.honorarios)
        h["valido_ate"] = (datetime.now(timezone.utc) - timedelta(days=2)).date().isoformat()
        s.honorarios = h
        db.commit()
    vencida = logado.post(aceite, json=corpo)
    assert vencida.status_code == 409 and "venceu em" in vencida.json()["detail"]
    assert logado.get(f"/api/portal/{token}").json()["simulacoes"][0]["honorarios"]["expirada"] is True
    # Renovada, aceita; depois não aceita de novo nem pode mudar
    logado.put(f"/api/simulacoes/{sim['id']}/honorarios", json=PROPOSTA)
    assert logado.post(aceite, json=corpo).status_code == 200
    assert logado.post(aceite, json=corpo).status_code == 409
    assert logado.put(f"/api/simulacoes/{sim['id']}/honorarios", json=PROPOSTA).status_code == 409
    assert logado.delete(f"/api/simulacoes/{sim['id']}/honorarios").status_code == 409
    # Despublicar o relatório tira a proposta do ar
    logado.patch(f"/api/simulacoes/{sim['id']}/publicacao", json={"publicada": False})
    assert logado.post(aceite, json=corpo).status_code == 404


def test_avisos_de_acompanhamento(logado: TestClient):
    cid, sim = _cenario(logado)
    logado.put(f"/api/simulacoes/{sim['id']}/honorarios", json=PROPOSTA)
    token = _publicar_e_gerar_link(logado, cid, sim["id"])
    codigos = lambda: {a["codigo"]: a for a in _avisos(logado)}  # noqa: E731
    assert "relatorio_nao_visto" not in codigos()                     # publicado agora
    with banco(logado) as db:
        db.get(Simulacao, sim["id"]).publicada_em = datetime.now(timezone.utc) - timedelta(days=4)
        db.commit()
    nao_visto = codigos()["relatorio_nao_visto"]
    assert nao_visto["gravidade"] == "info" and "há 4 dias" in nao_visto["detalhe"] and nao_visto["cliente_id"] == cid

    logado.post(f"/api/portal/{token}/simulacoes/{sim['id']}/visto")
    assert "relatorio_nao_visto" not in codigos() and "proposta_sem_resposta" not in codigos()
    with banco(logado) as db:
        db.get(Simulacao, sim["id"]).visto_primeira_em = datetime.now(timezone.utc) - timedelta(days=8)
        db.commit()
    sem_resposta = codigos()["proposta_sem_resposta"]
    assert sem_resposta["gravidade"] == "atencao" and "há 8 dias" in sem_resposta["titulo"] and sem_resposta["valor"] == 12120

    logado.post(f"/api/portal/{token}/simulacoes/{sim['id']}/aceite", json={"nome": "João da Silva", "confirmo": True})
    aceita = codigos()
    assert "proposta_sem_resposta" not in aceita
    assert aceita["proposta_aceita"]["gravidade"] == "oportunidade" and aceita["proposta_aceita"]["valor"] == 12120
    assert aceita["proposta_aceita"]["acao"]["aba"] == "dados" and "João da Silva aceitou" in aceita["proposta_aceita"]["titulo"]
    # Ao tornar o cliente ativo, o aviso de aceite some
    logado.patch(f"/api/clientes/{cid}", json={"status": "ativo"})
    assert "proposta_aceita" not in codigos()


def test_avisos_de_acompanhamento_com_varios_relatorios(logado: TestClient):
    cid, a = _cenario(logado)
    b = _planejar(logado, cid, COMERCIO)
    for s in (a, b):
        logado.patch(f"/api/simulacoes/{s['id']}/publicacao", json={"publicada": True})
    logado.post(f"/api/clientes/{cid}/portal", json={})
    with banco(logado) as db:
        for s in (a, b):
            db.get(Simulacao, s["id"]).publicada_em = datetime.now(timezone.utc) - timedelta(days=5)
        db.commit()
    nao_vistos = [x for x in _avisos(logado) if x["codigo"] == "relatorio_nao_visto"]
    assert len(nao_vistos) == 2 and len({x["id"] for x in nao_vistos}) == 2     # ids distintos para a tela


def test_portal_desativado_nao_gera_aviso_de_nao_visto(logado: TestClient):
    cid, sim = _cenario(logado)
    _publicar_e_gerar_link(logado, cid, sim["id"])
    with banco(logado) as db:
        db.get(Simulacao, sim["id"]).publicada_em = datetime.now(timezone.utc) - timedelta(days=5)
        db.commit()
    logado.delete(f"/api/clientes/{cid}/portal")
    assert not [a for a in _avisos(logado) if a["codigo"] == "relatorio_nao_visto"]


def test_honorarios_nao_vazam_entre_escritorios(logado: TestClient):
    cid, sim = _cenario(logado)
    logado.post("/api/auth/logout")
    cadastrar(logado, email="outra@escritorio.com.br", escritorio="Outro Escritório")
    assert logado.put(f"/api/simulacoes/{sim['id']}/honorarios", json=PROPOSTA).status_code == 404
    assert logado.get(f"/api/simulacoes/{sim['id']}/honorarios/sugestao").status_code == 404
    assert logado.delete(f"/api/simulacoes/{sim['id']}/honorarios").status_code == 404
    assert logado.get("/api/auth/me").json()["escritorio"]["honorarios"] is None
