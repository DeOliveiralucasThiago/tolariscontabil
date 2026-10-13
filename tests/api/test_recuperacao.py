from __future__ import annotations

from fastapi.testclient import TestClient

from tolaris_api.db import get_db
from tolaris_api.importacao import ler_nfe
from tolaris_api.models import DocumentoFiscal, ItemFiscal

from .conftest import CNPJ_VALIDO, cadastrar
from .test_importacao import CLIENTE_DO_CLIENTE, _enviar

# (ncm, cfop, icms, cst_pis, cest, valor, desconto, descrição)
Item = tuple[str, str, str, str, str, float, float, str]
REFRI: Item = ("22021000", "5405", "500", "49", "0300100", 10000.0, 0.0, "REFRIGERANTE COLA 2L")
COMUM: Item = ("19059090", "5102", "102", "49", "", 90000.0, 0.0, "BISCOITO")
COMUM_CHEIO: Item = ("19059090", "5102", "102", "49", "", 100000.0, 0.0, "BISCOITO")


def nfe_itens(numero: int, data: str, itens: list[Item], emit: str = CNPJ_VALIDO, dest: str = CLIENTE_DO_CLIENTE) -> bytes:
    chave = f"3526031122233300018155001{numero:09d}1{numero:08d}"[:43].ljust(43, "0") + "1"
    dets = ""
    for n, (ncm, cfop, icms, cst_pis, cest, valor, desc, nome) in enumerate(itens, start=1):
        # CST de PIS 04 fica no grupo PISNT; CSOSN de 3 dígitos é do Simples, CST de 2 dígitos do regime normal
        grupo_icms = (f"<ICMSSN{icms}><orig>0</orig><CSOSN>{icms}</CSOSN></ICMSSN{icms}>" if len(icms) == 3
                      else f"<ICMS{icms}><orig>0</orig><CST>{icms}</CST></ICMS{icms}>")
        grupo_pis = f"<PISNT><CST>{cst_pis}</CST></PISNT>" if cst_pis == "04" else f"<PISOutr><CST>{cst_pis}</CST></PISOutr>"
        dets += (f'<det nItem="{n}"><prod><cProd>{n}</cProd><xProd>{nome}</xProd><NCM>{ncm}</NCM>'
                 f'{f"<CEST>{cest}</CEST>" if cest else ""}<CFOP>{cfop}</CFOP><vProd>{valor:.2f}</vProd>'
                 f'<vDesc>{desc:.2f}</vDesc></prod><imposto><ICMS>{grupo_icms}</ICMS><PIS>{grupo_pis}</PIS></imposto></det>')
    total = sum(i[5] - i[6] for i in itens)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<nfeProc xmlns="http://www.portalfiscal.inf.br/nfe" versao="4.00"><NFe><infNFe Id="NFe{chave}" versao="4.00">
<ide><mod>55</mod><dhEmi>{data}T10:00:00-03:00</dhEmi><tpNF>1</tpNF></ide>
<emit><CNPJ>{emit}</CNPJ></emit><dest><CNPJ>{dest}</CNPJ></dest>{dets}
<total><ICMSTot><vICMS>0.00</vICMS><vIPI>0.00</vIPI><vPIS>0.00</vPIS><vCOFINS>0.00</vCOFINS><vNF>{total:.2f}</vNF></ICMSTot></total>
</infNFe></NFe><protNFe><infProt><chNFe>{chave}</chNFe><cStat>100</cStat></infProt></protNFe></nfeProc>""".encode()


def _cliente(c: TestClient, **extra) -> int:
    corpo = {"razao_social": "Mercadinho Boa Compra", "cnpj": CNPJ_VALIDO, "atividade": "comercio", "regime_atual": "simples"}
    return c.post("/api/clientes", json={**corpo, **extra}).json()["id"]


def _importar_13_meses(c: TestClient, cid: int) -> None:
    """Jan/2025 a jan/2026, R$ 100.000 por mês; só o último mês tem refrigerante (monofásico e ST)."""
    arquivos = []
    for i in range(13):
        ano, mes = 2025 + i // 12, i % 12 + 1
        itens = [COMUM_CHEIO] if i < 12 else [REFRI, COMUM]
        arquivos.append((f"n{i}.xml", nfe_itens(i + 1, f"{ano}-{mes:02d}-10", itens)))
    r = _enviar(c, cid, arquivos).json()
    assert r["importados"] == 13


def test_ler_nfe_soma_itens_e_le_csosn_cst_e_pis(logado: TestClient):
    xml = nfe_itens(1, "2026-01-10", [
        REFRI,
        ("22021000", "5405", "500", "49", "0300100", 500.0, 50.0, "REFRIGERANTE COLA 2L"),  # mesmo grupo: soma, com desconto
        ("30049099", "5102", "60", "04", "", 200.0, 0.0, "REMEDIO"),                          # CST (regime normal) e PIS 04
    ])
    itens = {(i.ncm, i.cst_icms, i.cst_pis): i for i in ler_nfe(xml, CNPJ_VALIDO).itens}
    refri = itens[("22021000", "500", "49")]
    assert refri.valor == 1_045_000 and refri.quantidade == 2 and refri.cest == "0300100" and refri.cfop == "5405"
    assert refri.descricao == "REFRIGERANTE COLA 2L"
    assert ("30049099", "60", "04") in itens


def test_nota_de_compra_nao_guarda_itens():
    xml = nfe_itens(2, "2026-01-10", [COMUM], emit=CLIENTE_DO_CLIENTE, dest=CNPJ_VALIDO)
    assert ler_nfe(xml, CNPJ_VALIDO).tipo == "entrada" and ler_nfe(xml, CNPJ_VALIDO).itens == []


def test_analise_de_recuperacao(logado: TestClient):
    cid = _cliente(logado)
    _importar_13_meses(logado, cid)
    r = logado.get(f"/api/clientes/{cid}/recuperacao").json()
    assert r["disponivel"] and r["anexo"] == "I" and r["anexo_origem"] == "atividade"
    assert r["periodo"] == {"inicio": "2025-01", "fim": "2026-01", "meses": 13}
    jan = r["meses"][-1]
    # RBT12 = 12 x 100.000 = 1.200.000 (4ª faixa): alíquota efetiva 8,825%
    assert jan["competencia"] == "2026-01" and jan["rbt12"] == 1_200_000 and jan["aliquota_efetiva"] == 0.08825
    assert jan["base_monofasico"] == 10_000 and jan["base_st"] == 10_000
    assert jan["pis_cofins"] == 136.79    # 10.000 x 8,825% x (2,76% + 12,74%)
    assert jan["icms"] == 295.64          # 10.000 x 8,825% x 33,5% = 295,6375
    assert r["totais"]["provavel"] == 432.43 and r["economia_anual"] == 432.43
    assert all(m["provavel"] == 0 for m in r["meses"][:-1])
    produto = r["produtos"][0]
    assert produto["ncm"] == "22021000" and produto["grupo"] == "Águas, refrigerantes, energéticos e cervejas"
    assert produto["valor"] == 10_000 and produto["certeza"] == "provavel"
    assert produto["monofasico"] == "NCM da lista" and produto["st"] == "ST indicado na nota"
    assert "Indício" in " ".join(r["alertas"]) and r["melhor"].startswith("R$ 432,43")
    # Anexo de indústria muda a repartição
    assert logado.get(f"/api/clientes/{cid}/recuperacao?anexo=II").json()["anexo"] == "II"
    assert logado.get(f"/api/clientes/{cid}/recuperacao?anexo=III").status_code == 422


def test_sem_itens_importados(logado: TestClient):
    cid = _cliente(logado)
    r = logado.get(f"/api/clientes/{cid}/recuperacao").json()
    assert r["disponivel"] is False and r["meses"] == [] and r["produtos"] == []
    salvar = logado.post(f"/api/clientes/{cid}/recuperacao", json={})
    assert salvar.status_code == 409 and "Importe os XML" in salvar.json()["detail"]


def test_avisos_de_atividade_e_regime(logado: TestClient):
    cid = _cliente(logado, atividade="servico_anexo_iii", regime_atual="presumido")
    _enviar(logado, cid, [("a.xml", nfe_itens(1, "2026-01-10", [REFRI]))])
    alertas = " ".join(logado.get(f"/api/clientes/{cid}/recuperacao").json()["alertas"])
    assert "usou o Anexo I" in alertas and "fora do Simples Nacional" in alertas


def test_reimportar_completa_notas_antigas_sem_itens(logado: TestClient):
    cid = _cliente(logado)
    xml = nfe_itens(9, "2026-01-10", [REFRI, COMUM])
    chave = ler_nfe(xml, CNPJ_VALIDO).chave
    sped = "\n".join([
        f"|0000|017|0|01012026|31012026|MERCADINHO|{CNPJ_VALIDO}||SP|1|3550308|||A|0|",
        f"|C100|1|0||55|00|1|9|{chave}|10012026|10012026|100000,00|0|0|0|100000,00|9|0|0|0|0|0|0|0|0|0|0|0|0|",
    ]).encode("latin-1")
    assert _enviar(logado, cid, [("efd.txt", sped)]).json()["importados"] == 1  # SPED sem C170: nota sem itens
    assert logado.get(f"/api/clientes/{cid}/recuperacao").json()["disponivel"] is False
    r = _enviar(logado, cid, [("nota.xml", xml)]).json()
    assert (r["importados"], r["duplicados"], r["atualizados"]) == (0, 1, 1)
    assert logado.get(f"/api/clientes/{cid}/recuperacao").json()["disponivel"] is True
    # Terceira vez: nada mais a completar
    assert _enviar(logado, cid, [("nota.xml", xml)]).json()["atualizados"] == 0


def test_mesma_nota_duas_vezes_no_mesmo_envio(logado: TestClient):
    cid = _cliente(logado)
    xml = nfe_itens(1, "2026-01-10", [REFRI])
    r = _enviar(logado, cid, [("a.xml", xml), ("b.xml", xml)]).json()
    assert (r["importados"], r["duplicados"], r["atualizados"]) == (1, 1, 0)


def test_sped_com_itens_c170(logado: TestClient):
    cid = _cliente(logado)
    sped = "\n".join([
        f"|0000|017|0|01012026|31012026|MERCADINHO|{CNPJ_VALIDO}||SP|1|3550308|||A|0|",
        "|0200|P1|REFRIGERANTE COLA 2L|||UN|00|22021000||||18|0300100|",
        "|0200|P2|BISCOITO|||UN|00|19059090||||18||",
        "|C100|1|0||55|00|1|5||10012026|10012026|1000,00|0|0|0|1000,00|9|0|0|0|0|0|0|0|0|0|0|0|0|",
        "|C170|1|P1||10|UN|600,00|0|0|060|5405||0|0|0|0|0|0||||0|0|0|0|49|0|0|0|0|0|49|0|0|0|0|0|",
        "|C170|2|P2||10|UN|450,00|50,00|0|000|5102||0|0|0|0|0|0||||0|0|0|0|49|0|0|0|0|0|49|0|0|0|0|0|",
        "|C100|1|0||55|02|1|6||11012026|11012026|999,00|0|0|0|999,00|9|0|0|0|0|0|0|0|0|0|0|0|0|",
        "|C170|1|P1||1|UN|999,00|0|0|060|5405||0|0|0|0|0|0||||0|0|0|0|49|0|0|0|0|0|49|0|0|0|0|0|",
    ]).encode("latin-1")
    assert _enviar(logado, cid, [("efd.txt", sped)]).json()["importados"] == 1
    r = logado.get(f"/api/clientes/{cid}/recuperacao").json()
    produto = r["produtos"][0]
    assert produto["ncm"] == "22021000" and produto["valor"] == 600 and produto["descricao"] == "REFRIGERANTE COLA 2L"
    assert produto["monofasico"] == "NCM da lista" and produto["st"] == "ST indicado na nota"  # CST 060 -> 60
    assert len(r["produtos"]) == 1  # o item comum e os da nota cancelada não aparecem


def test_salvar_como_simulacao(logado: TestClient):
    cid = _cliente(logado)
    _importar_13_meses(logado, cid)
    r = logado.post(f"/api/clientes/{cid}/recuperacao", json={})
    assert r.status_code == 201, r.text
    sim = r.json()
    assert sim["tipo"] == "recuperacao" and sim["titulo"] == "Recuperação de tributos — R$ 432,43 pagos a mais no período"
    assert sim["entrada"] == {"anexo": "I", "periodo_inicio": "2025-01", "periodo_fim": "2026-01"}
    assert sim["resultado"]["totais"]["provavel"] == 432.43
    assert [s["id"] for s in logado.get(f"/api/clientes/{cid}/simulacoes").json()] == [sim["id"]]


def test_apagar_documentos_apaga_itens(logado: TestClient):
    cid = _cliente(logado)
    _importar_13_meses(logado, cid)
    assert logado.delete(f"/api/clientes/{cid}/documentos?competencia=2026-01").status_code == 204
    r = logado.get(f"/api/clientes/{cid}/recuperacao").json()
    assert r["periodo"]["fim"] == "2025-12" and r["totais"]["provavel"] == 0
    logado.delete(f"/api/clientes/{cid}/documentos")
    assert logado.get(f"/api/clientes/{cid}/recuperacao").json()["disponivel"] is False


def test_excluir_cliente_apaga_documentos_e_itens(logado: TestClient):
    cid = _cliente(logado)
    _importar_13_meses(logado, cid)
    assert logado.delete(f"/api/clientes/{cid}").status_code == 204
    db = next(logado.app.dependency_overrides[get_db]())
    try:
        assert db.query(DocumentoFiscal).count() == 0 and db.query(ItemFiscal).count() == 0
    finally:
        db.close()  # sem fechar, o PostgreSQL mantém a transação aberta e trava o drop_all do teardown


def test_outro_escritorio_nao_enxerga(logado: TestClient):
    cid = _cliente(logado)
    _importar_13_meses(logado, cid)
    logado.post("/api/auth/logout")
    cadastrar(logado, email="outra@escritorio.com.br", escritorio="Outro Escritório")
    assert logado.get(f"/api/clientes/{cid}/recuperacao").status_code == 404
    assert logado.post(f"/api/clientes/{cid}/recuperacao", json={}).status_code == 404


def test_relatorio_em_pdf(logado: TestClient):
    from io import BytesIO

    from pypdf import PdfReader

    cid = _cliente(logado)
    _importar_13_meses(logado, cid)
    sim = logado.post(f"/api/clientes/{cid}/recuperacao", json={}).json()
    pdf = logado.get(f"/api/simulacoes/{sim['id']}/proposta.pdf")
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    texto = "\n".join(p.extract_text() or "" for p in PdfReader(BytesIO(pdf.content)).pages)
    assert "Recuperação de tributos no Simples Nacional" in texto
    assert "R$ 432,43" in texto and "REFRIGERANTE COLA 2L" in texto and "22021000" in texto
    assert "Indício, não certeza" in texto
