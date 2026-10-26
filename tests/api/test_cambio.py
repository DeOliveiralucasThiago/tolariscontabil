from __future__ import annotations

from datetime import date
from decimal import Decimal

import httpx
import pytest
from fastapi.testclient import TestClient

from tolaris_api import cambio
from tolaris_api.main import app
from tolaris_api.routers.cambio import get_consulta_ptax, get_lista_moedas

BOLETINS = [
    {"cotacaoCompra": 3.9500, "cotacaoVenda": 3.9510, "dataHoraCotacao": "2026-10-15 10:08:40.123", "tipoBoletim": "Abertura"},
    {"cotacaoCompra": 3.9700, "cotacaoVenda": 3.9710, "dataHoraCotacao": "2026-10-15 13:06:11.5", "tipoBoletim": "Fechamento"},
    {"cotacaoCompra": 3.9000, "cotacaoVenda": 3.9010, "dataHoraCotacao": "2026-10-14 13:06:11.5", "tipoBoletim": "Fechamento"},
    {"cotacaoCompra": 0, "cotacaoVenda": 0, "dataHoraCotacao": "2026-10-16 10:00:00.0", "tipoBoletim": "Abertura"},  # inválida
    {"dataHoraCotacao": "lixo"},
]


def test_escolhe_o_fechamento_do_ultimo_dia_util():
    p = cambio.escolher_cotacao("CAD", date(2026, 10, 15), BOLETINS)
    assert (p.data_cotacao, p.compra, p.venda, p.boletim) == (date(2026, 10, 15), Decimal("3.97"), Decimal("3.971"), "Fechamento")
    # sábado 17: vale a sexta 16? a de 16 é inválida; volta ao dia 15
    p2 = cambio.escolher_cotacao("CAD", date(2026, 10, 17), BOLETINS)
    assert p2.data_cotacao == date(2026, 10, 15) and p2.como_dict()["dia_anterior"] is True
    with pytest.raises(cambio.CotacaoNaoEncontrada):
        cambio.escolher_cotacao("CAD", date(2026, 10, 1), BOLETINS)


def test_consulta_o_banco_central_com_a_janela_e_as_datas_no_formato_dele():
    visto = {}

    def handler(req: httpx.Request) -> httpx.Response:
        visto["url"], visto["q"] = str(req.url.path), dict(req.url.params)
        return httpx.Response(200, json={"value": BOLETINS})

    p = cambio.consultar_ptax("cad", date(2026, 10, 15), transport=httpx.MockTransport(handler))
    assert p.moeda == "CAD" and p.compra == Decimal("3.97")
    assert "CotacaoMoedaPeriodo" in visto["url"]
    assert visto["q"]["@moeda"] == "'CAD'" and visto["q"]["@dataFinalCotacao"] == "'10-15-2026'" and visto["q"]["@dataInicial"] == "'10-05-2026'"


def test_erros_do_banco_central():
    com = lambda h: httpx.MockTransport(h)  # noqa: E731
    with pytest.raises(cambio.CambioIndisponivel):
        cambio.consultar_ptax("USD", date(2026, 10, 15), transport=com(lambda r: httpx.Response(500)))
    with pytest.raises(cambio.CambioIndisponivel):
        cambio.consultar_ptax("USD", date(2026, 10, 15), transport=com(lambda r: httpx.Response(200, json={"x": 1})))
    with pytest.raises(cambio.CambioIndisponivel):
        cambio.consultar_ptax("USD", date(2026, 10, 15), transport=com(lambda r: (_ for _ in ()).throw(httpx.ConnectError("sem rede"))))
    with pytest.raises(cambio.CotacaoNaoEncontrada):
        cambio.consultar_ptax("USD", date(2026, 10, 15), transport=com(lambda r: httpx.Response(200, json={"value": []})))
    with pytest.raises(cambio.CotacaoNaoEncontrada):  # código fora do formato nem chega ao Banco Central
        cambio.consultar_ptax("X1", date(2026, 10, 15))
    # moeda fora das dez comuns: o Banco Central decide
    p = cambio.consultar_ptax("ZAR", date(2026, 10, 15), transport=com(lambda r: httpx.Response(200, json={"value": BOLETINS})))
    assert p.moeda == "ZAR" and p.como_dict()["nome"] == "ZAR"


MOEDAS_BCB = {
    "value": [
        {"simbolo": "USD", "nomeFormatado": "DOLAR DOS EUA", "tipoMoeda": "A"},
        {"simbolo": "ZAR", "nomeFormatado": "RAND", "tipoMoeda": "A"},
        {"simbolo": "ARS", "nomeFormatado": "PESO ARGENTINO", "tipoMoeda": "A"},
        {"simbolo": "BRL", "nomeFormatado": "REAL", "tipoMoeda": "A"},
        {"simbolo": "lixo!"},
        {"nomeFormatado": "sem símbolo"},
    ]
}


@pytest.fixture
def sem_cache(monkeypatch):
    monkeypatch.setattr(cambio, "_lista_guardada", None)


def test_lista_de_moedas_vem_do_banco_central_e_fica_guardada(sem_cache):
    chamadas = []

    def handler(req: httpx.Request) -> httpx.Response:
        chamadas.append(req.url.path)
        return httpx.Response(200, json=MOEDAS_BCB)

    lista = cambio.listar_moedas(transport=httpx.MockTransport(handler))
    assert list(lista) == ["USD", "ARS", "ZAR"]  # comuns primeiro, depois ordem alfabética do nome
    assert lista["USD"] == "Dólar dos EUA" and lista["ZAR"] == "Rand" and "BRL" not in lista
    assert chamadas[0].endswith("/Moedas")
    cambio.listar_moedas(transport=httpx.MockTransport(handler))  # segunda vez: do cache
    assert len(chamadas) == 1
    assert cambio.nome_da_moeda("ZAR") == "Rand" and cambio.nome_da_moeda("QQQ") == "QQQ"


def test_lista_de_moedas_cai_para_as_comuns_quando_o_banco_central_falha(sem_cache):
    com = lambda h: httpx.MockTransport(h)  # noqa: E731
    assert cambio.listar_moedas(transport=com(lambda r: httpx.Response(500))) == cambio.MOEDAS
    assert cambio.listar_moedas(transport=com(lambda r: httpx.Response(200, json={"x": 1}))) == cambio.MOEDAS
    assert cambio.listar_moedas(transport=com(lambda r: httpx.Response(200, json={"value": []}))) == cambio.MOEDAS
    assert cambio._lista_guardada is None  # falha não fica guardada


def test_rota_exige_login_e_usa_a_consulta(logado: TestClient):
    anonimo = TestClient(logado.app)
    assert anonimo.get("/api/cambio/ptax?moeda=CAD&data=2026-10-15").status_code == 401
    assert anonimo.get("/api/cambio/moedas").status_code == 401
    app.dependency_overrides[get_lista_moedas] = lambda: (lambda: {"USD": "Dólar", "CAD": "Dólar canadense", "ZAR": "Rand"})
    assert [m["codigo"] for m in logado.get("/api/cambio/moedas").json()] == ["USD", "CAD", "ZAR"]

    chamadas = []

    def falsa(moeda: str, data: date) -> cambio.Ptax:
        chamadas.append((moeda, data))
        return cambio.escolher_cotacao(moeda, data, BOLETINS)

    app.dependency_overrides[get_consulta_ptax] = lambda: falsa
    r = logado.get("/api/cambio/ptax?moeda=cad&data=2026-10-15")
    assert r.status_code == 200 and r.json()["compra"] == 3.97 and r.json()["moeda"] == "CAD" and chamadas == [("CAD", date(2026, 10, 15))]
    assert logado.get("/api/cambio/ptax?moeda=XXX&data=2026-10-15").status_code == 422
    assert logado.get("/api/cambio/ptax?moeda=zar&data=2026-10-15").status_code == 200  # fora das dez comuns, mas listada
    assert logado.get("/api/cambio/ptax?moeda=CAD&data=2999-01-01").status_code == 422
    assert logado.get("/api/cambio/ptax?moeda=CAD&data=ontem").status_code == 422

    def sem_cotacao(moeda, data):
        raise cambio.CotacaoNaoEncontrada("x")

    def fora(moeda, data):
        raise cambio.CambioIndisponivel("x")

    app.dependency_overrides[get_consulta_ptax] = lambda: sem_cotacao
    assert logado.get("/api/cambio/ptax?moeda=CAD&data=2026-10-01").status_code == 404
    app.dependency_overrides[get_consulta_ptax] = lambda: fora
    r = logado.get("/api/cambio/ptax?moeda=CAD&data=2026-10-01")
    assert r.status_code == 502 and "manualmente" in r.json()["detail"]
