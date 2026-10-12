from __future__ import annotations

import io
import zipfile

from fastapi.testclient import TestClient

from tolaris_api.importacao import ler_nfe

from .conftest import CNPJ_VALIDO, cadastrar

FORNECEDOR = "11444777000161"
CLIENTE_DO_CLIENTE = "45997418000153"


def nfe(numero: int, emit: str, dest: str, data: str = "2026-03-10", valor: str = "1000.00", tp_nf: str = "1",
        status: str = "100", icms: str = "180.00") -> bytes:
    chave = f"3526031122233300018155001{numero:09d}1{numero:08d}"[:43].ljust(43, "0") + "1"
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<nfeProc xmlns="http://www.portalfiscal.inf.br/nfe" versao="4.00">
  <NFe><infNFe Id="NFe{chave}" versao="4.00">
    <ide><mod>55</mod><dhEmi>{data}T10:00:00-03:00</dhEmi><tpNF>{tp_nf}</tpNF></ide>
    <emit><CNPJ>{emit}</CNPJ></emit>
    <dest><CNPJ>{dest}</CNPJ></dest>
    <total><ICMSTot><vICMS>{icms}</vICMS><vIPI>0.00</vIPI><vPIS>6.50</vPIS><vCOFINS>30.00</vCOFINS><vNF>{valor}</vNF></ICMSTot></total>
  </infNFe></NFe>
  <protNFe><infProt><chNFe>{chave}</chNFe><cStat>{status}</cStat></infProt></protNFe>
</nfeProc>""".encode()


def sped(cnpj: str = CNPJ_VALIDO) -> bytes:
    linhas = [
        f"|0000|017|0|01032026|31032026|PADARIA PAO BOM LTDA|{cnpj}||SP|123|3550308|||A|0|",
        f"|0150|F001|FORNECEDOR SA|01058|{FORNECEDOR}||||||||",
        # Saída regular sem chave (modelo 01), entrada de fornecedor, e uma nota cancelada
        "|C100|1|0||01|00|1|123||15032026|15032026|2500,00|0|0|0|2500,00|9|0|0|0|2500,00|450,00|0|0|0|16,25|75,00|0|0|",
        "|C100|0|1|F001|55|00|1|777||20032026|21032026|800,00|0|0|0|800,00|9|0|0|0|800,00|144,00|0|0|40,00|5,20|24,00|0|0|",
        "|C100|1|0||55|02|1|124||16032026|16032026|999,00|0|0|0|999,00|9|0|0|0|0|0|0|0|0|0|0|0|0|",
        "|9999|5|",
    ]
    return "\n".join(linhas).encode("latin-1")


def _cliente(c: TestClient, cnpj: str | None = CNPJ_VALIDO) -> int:
    return c.post("/api/clientes", json={"razao_social": "Padaria Pão Bom", "cnpj": cnpj}).json()["id"]


def _enviar(c: TestClient, cid: int, arquivos: list[tuple[str, bytes]]):
    return c.post(f"/api/clientes/{cid}/importacoes", files=[("arquivos", (n, b)) for n, b in arquivos])


def test_nfe_saida_entrada_e_ignoradas(logado: TestClient):
    cid = _cliente(logado)
    r = _enviar(logado, cid, [
        ("venda.xml", nfe(1, CNPJ_VALIDO, CLIENTE_DO_CLIENTE, valor="1000.00")),
        ("compra.xml", nfe(2, FORNECEDOR, CNPJ_VALIDO, valor="400.00", icms="72.00")),
        ("alheia.xml", nfe(3, FORNECEDOR, CLIENTE_DO_CLIENTE)),
        ("cancelada.xml", nfe(4, CNPJ_VALIDO, CLIENTE_DO_CLIENTE, status="101")),
        ("planilha.csv", b"a;b"),
    ]).json()
    assert r["importados"] == 2 and r["duplicados"] == 0 and r["competencias"] == ["2026-03"]
    motivos = {i["arquivo"]: i["motivo"] for i in r["ignorados"]}
    assert "nem destinatário" in motivos["alheia.xml"]
    assert "não autorizada" in motivos["cancelada.xml"]
    assert "Formato não suportado" in motivos["planilha.csv"]
    mov = logado.get(f"/api/clientes/{cid}/movimento").json()
    assert mov["meses"] == [{"competencia": "2026-03", "saidas": 1000.0, "entradas": 400.0, "icms": 180.0,
                             "ipi": 0.0, "pis": 6.5, "cofins": 30.0, "documentos": 2}]
    assert mov["receita_12m"] == 1000.0 and mov["compras_12m"] == 400.0


def test_reimportar_nao_duplica(logado: TestClient):
    cid = _cliente(logado)
    _enviar(logado, cid, [("a.xml", nfe(1, CNPJ_VALIDO, CLIENTE_DO_CLIENTE))])
    r = _enviar(logado, cid, [("a.xml", nfe(1, CNPJ_VALIDO, CLIENTE_DO_CLIENTE))]).json()
    assert r["importados"] == 0 and r["duplicados"] == 1


def test_zip_com_varias_notas_e_zip_aninhado(logado: TestClient):
    cid = _cliente(logado)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for i in range(1, 6):
            zf.writestr(f"notas/{i}.xml", nfe(i, CNPJ_VALIDO, CLIENTE_DO_CLIENTE, data=f"2026-0{i}-05"))
        zf.writestr("dentro.zip", b"PK")
    r = _enviar(logado, cid, [("lote.zip", buf.getvalue())]).json()
    assert r["importados"] == 5 and r["competencias"] == [f"2026-0{i}" for i in range(1, 6)]
    assert any("ZIP dentro de ZIP" in i["motivo"] for i in r["ignorados"])
    assert _enviar(logado, cid, [("ruim.zip", b"isto nao e zip")]).json()["ignorados"][0]["motivo"] == "ZIP corrompido"


def test_xml_malicioso_nao_e_processado(logado: TestClient):
    cid = _cliente(logado)
    xxe = b"""<?xml version="1.0"?><!DOCTYPE x [<!ENTITY e SYSTEM "file:///etc/passwd">]><nfeProc>&e;</nfeProc>"""
    bomba = b"""<?xml version="1.0"?><!DOCTYPE l [<!ENTITY a "aaaa"><!ENTITY b "&a;&a;&a;&a;">]><r>&b;</r>"""
    r = _enviar(logado, cid, [("xxe.xml", xxe), ("bomba.xml", bomba)]).json()
    assert r["importados"] == 0 and all("inseguro" in i["motivo"] for i in r["ignorados"])


def test_sped_fiscal(logado: TestClient):
    cid = _cliente(logado)
    r = _enviar(logado, cid, [("efd_032026.txt", sped())]).json()
    assert r["importados"] == 2  # a cancelada fica de fora
    mes = logado.get(f"/api/clientes/{cid}/movimento").json()["meses"][0]
    assert (mes["saidas"], mes["entradas"], mes["icms"], mes["pis"], mes["cofins"]) == (2500.0, 800.0, 450.0, 16.25, 75.0)
    outro = _enviar(logado, cid, [("outro.txt", sped(cnpj=FORNECEDOR))]).json()
    assert outro["importados"] == 0 and "outro CNPJ" in outro["ignorados"][0]["motivo"]


def test_sped_e_xml_da_mesma_nota_nao_somam_duas_vezes(logado: TestClient):
    cid = _cliente(logado)
    xml = nfe(9, CNPJ_VALIDO, CLIENTE_DO_CLIENTE)
    chave = ler_nfe(xml, CNPJ_VALIDO).chave
    linhas = [
        f"|0000|017|0|01032026|31032026|PADARIA|{CNPJ_VALIDO}||SP|1|3550308|||A|0|",
        f"|C100|1|0||55|00|1|9|{chave}|10032026|10032026|1000,00|0|0|0|1000,00|9|0|0|0|1000,00|180,00|0|0|0|6,50|30,00|0|0|",
    ]
    _enviar(logado, cid, [("nota.xml", xml)])
    r = _enviar(logado, cid, [("efd.txt", "\n".join(linhas).encode("latin-1"))]).json()
    assert r["importados"] == 0 and r["duplicados"] == 1


def test_cliente_sem_cnpj_limite_e_isolamento(client: TestClient, monkeypatch):
    cadastrar(client, "a@a.com", "Escritório A")
    sem_cnpj = _cliente(client, cnpj=None)
    assert _enviar(client, sem_cnpj, [("a.xml", b"<x/>")]).status_code == 400
    cid = _cliente(client)
    from tolaris_api.config import get_settings

    monkeypatch.setattr(get_settings(), "importacao_max_mb", 0)
    assert _enviar(client, cid, [("a.xml", nfe(1, CNPJ_VALIDO, CLIENTE_DO_CLIENTE))]).status_code == 413
    monkeypatch.undo()
    client.post("/api/auth/logout")
    cadastrar(client, "b@b.com", "Escritório B")
    assert _enviar(client, cid, [("a.xml", nfe(1, CNPJ_VALIDO, CLIENTE_DO_CLIENTE))]).status_code == 404
    assert client.get(f"/api/clientes/{cid}/movimento").status_code == 404


def test_apagar_documentos_por_competencia(logado: TestClient):
    cid = _cliente(logado)
    _enviar(logado, cid, [("1.xml", nfe(1, CNPJ_VALIDO, CLIENTE_DO_CLIENTE, data="2026-01-05")),
                          ("2.xml", nfe(2, CNPJ_VALIDO, CLIENTE_DO_CLIENTE, data="2026-02-05"))])
    assert logado.delete(f"/api/clientes/{cid}/documentos?competencia=2026-01").status_code == 204
    assert [m["competencia"] for m in logado.get(f"/api/clientes/{cid}/movimento").json()["meses"]] == ["2026-02"]
    assert logado.delete(f"/api/clientes/{cid}/documentos?competencia=jan").status_code == 422
