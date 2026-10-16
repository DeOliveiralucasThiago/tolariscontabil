"""Caixa de entrada de notas por e-mail (IMAP) com um servidor IMAP de mentira."""

from __future__ import annotations

import imaplib
import io
import socket
import zipfile
from datetime import timedelta
from email.message import EmailMessage

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from tolaris_api import caixa_email as servico
from tolaris_api.acesso import agora
from tolaris_api.config import get_settings
from tolaris_api.db import get_db
from tolaris_api.models import CaixaEmail, DocumentoFiscal, Usuario

from .conftest import CNPJ_VALIDO, cadastrar
from .test_importacao import CLIENTE_DO_CLIENTE, FORNECEDOR, nfe, sped

CORPO = {"host": "imap.exemplo.com.br", "porta": 993, "usuario": "notas@escritorio.com.br", "senha": "segredo-da-caixa", "pasta": "INBOX"}


def mensagem(assunto: str, anexos: list[tuple[str, bytes]] | None = None) -> bytes:
    m = EmailMessage()
    m["Subject"], m["From"], m["To"] = assunto, "cliente@exemplo.com.br", "notas@escritorio.com.br"
    m.set_content("Segue em anexo.")
    for nome, dados in anexos or []:
        m.add_attachment(dados, maintype="application", subtype="octet-stream", filename=nome)
    return m.as_bytes()


def zip_de(arquivos: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for n, d in arquivos.items():
            z.writestr(n, d)
    return buf.getvalue()


class ImapFalso:
    """Imita só o que o serviço usa do imaplib."""

    def __init__(self, mensagens: dict[int, bytes], validade: int = 7, senha_ok: bool = True, pasta_ok: bool = True) -> None:
        self.mensagens, self.validade, self.senha_ok, self.pasta_ok = mensagens, validade, senha_ok, pasta_ok
        self.buscas: list[tuple] = []
        self.somente_leitura = None
        self.saiu = False

    def login(self, usuario: str, senha: str) -> None:
        assert senha == "segredo-da-caixa"
        if not self.senha_ok:
            raise imaplib.IMAP4.error("[AUTHENTICATIONFAILED] senha")

    def select(self, pasta: str, readonly: bool = False):
        self.somente_leitura = readonly
        return ("OK" if self.pasta_ok else "NO"), [b"1"]

    def response(self, nome: str):
        return nome, [str(self.validade).encode()]

    def uid(self, comando: str, *args):
        if comando == "SEARCH":
            self.buscas.append(args)
            todos = sorted(self.mensagens)
            if args[1] == "UID":  # "N:*": o servidor sempre devolve ao menos a última
                inicio = int(args[2].split(":")[0])
                achados = [u for u in todos if u >= inicio] or todos[-1:]
            else:
                achados = todos
            return "OK", [b" ".join(str(u).encode() for u in achados)]
        uid = int(args[0])
        bruto = self.mensagens[uid]
        if "RFC822.SIZE" in args[1]:
            return "OK", [f"{uid} (UID {uid} RFC822.SIZE {len(bruto)})".encode()]
        assert "PEEK" in args[1]  # nunca marca como lida
        return "OK", [(f"{uid} (UID {uid} BODY[] {{{len(bruto)}}}".encode(), bruto), b")"]

    def logout(self) -> None:
        self.saiu = True


@pytest.fixture(autouse=True)
def dns_publico(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", lambda host, porta, **kw: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", porta))])


@pytest.fixture()
def banco(logado: TestClient):
    db = next(logado.app.dependency_overrides[get_db]())
    yield db
    db.close()


def _cliente(c: TestClient, cnpj: str, nome: str) -> int:
    return c.post("/api/clientes", json={"razao_social": nome, "cnpj": cnpj}).json()["id"]


def _salvar(c: TestClient, **extra):
    return c.put("/api/escritorio/caixa-email", json={**CORPO, **extra})


def _caixa(db) -> CaixaEmail:
    db.expire_all()
    return db.scalar(select(CaixaEmail))


def _notas(db, cliente_id: int) -> int:
    return len(db.scalars(select(DocumentoFiscal).where(DocumentoFiscal.cliente_id == cliente_id)).all())


def _verificar(c: TestClient, monkeypatch, imap: ImapFalso):
    monkeypatch.setattr(servico, "abrir_conexao", lambda host, porta: imap)
    r = c.post("/api/escritorio/caixa-email/verificar")
    assert r.status_code == 200, r.text
    return r.json()["ultimo_resultado"]


# --- Configuração ---------------------------------------------------------------------------------------
def test_configurar_guarda_a_senha_cifrada_e_nunca_a_devolve(logado: TestClient, banco):
    assert logado.get("/api/escritorio/caixa-email").json()["configurada"] is False
    r = _salvar(logado)
    assert r.status_code == 200, r.text
    corpo = r.json()
    assert corpo["configurada"] and corpo["host"] == "imap.exemplo.com.br" and "senha" not in corpo
    assert "segredo-da-caixa" not in r.text
    assert "segredo-da-caixa" not in _caixa(banco).senha_cifrada
    assert logado.get("/api/escritorio/caixa-email").json()["usuario"] == "notas@escritorio.com.br"


def test_primeira_vez_e_troca_de_servidor_exigem_senha(logado: TestClient):
    assert _salvar(logado, senha=None).status_code == 400
    assert _salvar(logado).status_code == 200
    # só liga/desliga e muda a pasta: mantém a senha guardada
    assert _salvar(logado, senha=None, ativo=False, pasta="Notas").status_code == 200
    # outro servidor com a senha guardada seguindo junto seria vazamento
    r = _salvar(logado, senha=None, host="outro.exemplo.com")
    assert r.status_code == 400 and "senha" in r.json()["detail"]
    assert _salvar(logado, senha=None, usuario="outro@escritorio.com.br").status_code == 400


def test_so_administrador_mexe_na_caixa(logado: TestClient, banco):
    _salvar(logado)
    usuario = banco.scalar(select(Usuario))
    usuario.papel = "contador"
    banco.commit()
    assert logado.get("/api/escritorio/caixa-email").status_code == 403
    assert _salvar(logado).status_code == 403
    assert logado.post("/api/escritorio/caixa-email/verificar").status_code == 403
    assert TestClient(logado.app).get("/api/escritorio/caixa-email").status_code == 401


def test_remover_e_verificar_sem_configurar(logado: TestClient):
    assert logado.post("/api/escritorio/caixa-email/verificar").status_code == 404
    _salvar(logado)
    assert logado.delete("/api/escritorio/caixa-email").status_code == 204
    assert logado.get("/api/escritorio/caixa-email").json()["configurada"] is False


@pytest.mark.parametrize("ip,aceito", [
    ("93.184.216.34", True), ("127.0.0.1", False), ("10.1.2.3", False), ("192.168.0.9", False),
    ("169.254.169.254", False), ("::1", False), ("172.16.0.1", False),
])
def test_ssrf_bloqueia_redes_internas(monkeypatch, ip, aceito):
    monkeypatch.setattr(socket, "getaddrinfo", lambda host, porta, **kw: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, porta))])
    if aceito:
        assert servico.validar_destino("imap.exemplo.com", 993) == ip
    else:
        with pytest.raises(servico.ErroCaixa, match="rede interna"):
            servico.validar_destino("imap.exemplo.com", 993)


def test_ssrf_host_porta_e_excecao_configurada(monkeypatch, logado: TestClient):
    for ruim in ("", "a b", "http://x.com", "x.com/../", "-x.com", "x_y.com", "a" * 300):
        with pytest.raises(servico.ErroCaixa):
            servico.validar_destino(ruim, 993)
    with pytest.raises(servico.ErroCaixa, match="993"):
        servico.validar_destino("imap.exemplo.com", 6379)  # porta de outro serviço
    assert _salvar(logado, porta=25).status_code == 400
    monkeypatch.setattr(socket, "getaddrinfo", lambda host, porta, **kw: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.5", porta))])
    assert _salvar(logado).status_code == 400
    monkeypatch.setenv("TOLARIS_IMAP_PERMITIR_REDE_PRIVADA", "true")
    get_settings.cache_clear()
    try:
        assert _salvar(logado, porta=143).status_code == 200
    finally:
        monkeypatch.delenv("TOLARIS_IMAP_PERMITIR_REDE_PRIVADA")
        get_settings.cache_clear()


def test_host_que_nao_resolve(monkeypatch, logado: TestClient):
    def falha(*a, **k):
        raise socket.gaierror
    monkeypatch.setattr(socket, "getaddrinfo", falha)
    r = _salvar(logado)
    assert r.status_code == 400 and "servidor" in r.json()["detail"]


# --- Leitura das mensagens -----------------------------------------------------------------------------------
def test_importa_anexos_e_acha_o_cliente_pelo_cnpj(logado: TestClient, banco, monkeypatch):
    a = _cliente(logado, CNPJ_VALIDO, "Padaria Pão Bom")
    b = _cliente(logado, FORNECEDOR, "Atacado Silva")
    _salvar(logado)
    imap = ImapFalso({
        1: mensagem("Notas de março", [("n1.xml", nfe(1, CNPJ_VALIDO, CLIENTE_DO_CLIENTE))]),
        2: mensagem("Pacote do atacado", [("notas.zip", zip_de({"a.xml": nfe(2, FORNECEDOR, CLIENTE_DO_CLIENTE), "b.xml": nfe(3, FORNECEDOR, CLIENTE_DO_CLIENTE)}))]),
        3: mensagem("SPED", [("sped.txt", sped(CNPJ_VALIDO))]),
        4: mensagem("Só conversa"),
        5: mensagem("Nota de gente que não é cliente", [("x.xml", nfe(9, "11111111000191", CLIENTE_DO_CLIENTE))]),
        6: mensagem("Planilha", [("dados.xlsx", b"PK"), ("foto.png", b"\x89PNG")]),
    })
    r = _verificar(logado, monkeypatch, imap)
    assert r["ok"] and r["erro"] is None
    assert r["mensagens"] == 6 and r["com_anexos"] == 3 + 1  # xml, zip, sped e a nota de desconhecido
    assert _notas(banco, b) == 2
    assert _notas(banco, a) == 1 + 2  # xml + 2 saídas/entradas válidas do SPED
    assert r["sem_cliente"] == ["Nota de gente que não é cliente"]
    assert {x["cliente"]: x["importados"] for x in r["por_cliente"]} == {"Padaria Pão Bom": 3, "Atacado Silva": 2}
    assert imap.somente_leitura is True and imap.saiu
    caixa = _caixa(banco)
    assert caixa.ultimo_uid == 6 and caixa.uid_validade == 7 and caixa.ultima_verificacao_em is not None


def test_segunda_leitura_so_pega_mensagens_novas(logado: TestClient, banco, monkeypatch):
    a = _cliente(logado, CNPJ_VALIDO, "Padaria Pão Bom")
    _salvar(logado)
    msgs = {1: mensagem("um", [("n1.xml", nfe(1, CNPJ_VALIDO, CLIENTE_DO_CLIENTE))])}
    r1 = _verificar(logado, monkeypatch, ImapFalso(msgs))
    assert r1["importados"] == 1
    r2 = _verificar(logado, monkeypatch, ImapFalso(msgs))
    assert r2["mensagens"] == 0 and r2["importados"] == 0
    msgs[2] = mensagem("dois", [("n2.xml", nfe(2, CNPJ_VALIDO, CLIENTE_DO_CLIENTE))])
    imap = ImapFalso(msgs)
    r3 = _verificar(logado, monkeypatch, imap)
    assert r3["mensagens"] == 1 and r3["importados"] == 1 and imap.buscas[0][1:] == ("UID", "2:*")
    assert _notas(banco, a) == 2


def test_primeira_leitura_olha_so_a_janela_inicial(logado: TestClient, monkeypatch):
    _cliente(logado, CNPJ_VALIDO, "Padaria Pão Bom")
    _salvar(logado)
    imap = ImapFalso({1: mensagem("um")})
    _verificar(logado, monkeypatch, imap)
    assert imap.buscas[0][1] == "SINCE"
    dia, mes, ano = imap.buscas[0][2].split("-")
    assert len(dia) == 2 and mes in servico.MESES_IMAP and len(ano) == 4


def test_mudou_a_validade_dos_uids_le_de_novo_sem_duplicar(logado: TestClient, banco, monkeypatch):
    a = _cliente(logado, CNPJ_VALIDO, "Padaria Pão Bom")
    _salvar(logado)
    msgs = {1: mensagem("um", [("n1.xml", nfe(1, CNPJ_VALIDO, CLIENTE_DO_CLIENTE))])}
    _verificar(logado, monkeypatch, ImapFalso(msgs, validade=7))
    r = _verificar(logado, monkeypatch, ImapFalso(msgs, validade=8))
    assert r["mensagens"] == 1 and r["importados"] == 0 and r["duplicados"] == 1
    assert _caixa(banco).uid_validade == 8 and _notas(banco, a) == 1


def test_nota_entre_dois_clientes_entra_nos_dois(logado: TestClient, banco, monkeypatch):
    a = _cliente(logado, CNPJ_VALIDO, "Padaria Pão Bom")
    b = _cliente(logado, FORNECEDOR, "Atacado Silva")
    _salvar(logado)
    r = _verificar(logado, monkeypatch, ImapFalso({1: mensagem("venda", [("n.xml", nfe(1, FORNECEDOR, CNPJ_VALIDO))])}))
    assert r["importados"] == 2 and _notas(banco, a) == 1 and _notas(banco, b) == 1


def test_no_maximo_50_mensagens_por_rodada(logado: TestClient, banco, monkeypatch):
    a = _cliente(logado, CNPJ_VALIDO, "Padaria Pão Bom")
    _salvar(logado)
    msgs = {i: mensagem(f"m{i}", [(f"n{i}.xml", nfe(i, CNPJ_VALIDO, CLIENTE_DO_CLIENTE))]) for i in range(1, 56)}
    assert _verificar(logado, monkeypatch, ImapFalso(msgs))["mensagens"] == 50
    assert _caixa(banco).ultimo_uid == 50
    assert _verificar(logado, monkeypatch, ImapFalso(msgs))["mensagens"] == 5
    assert _notas(banco, a) == 55


def test_senha_errada_pasta_inexistente_e_falha_de_rede(logado: TestClient, banco, monkeypatch):
    _cliente(logado, CNPJ_VALIDO, "Padaria Pão Bom")
    _salvar(logado)
    r = _verificar(logado, monkeypatch, ImapFalso({}, senha_ok=False))
    assert r["ok"] is False and "senha" in r["erro"] and "aplicativo" in r["erro"]
    r = _verificar(logado, monkeypatch, ImapFalso({}, pasta_ok=False))
    assert r["ok"] is False and "Pasta" in r["erro"]

    def cai(host, porta):
        raise OSError("connection reset")
    monkeypatch.setattr(servico, "abrir_conexao", cai)
    r = logado.post("/api/escritorio/caixa-email/verificar").json()["ultimo_resultado"]
    assert r["ok"] is False and "comunicação" in r["erro"]
    assert _caixa(banco).ultimo_uid is None  # erro não avança o progresso


def test_erro_inesperado_nao_derruba_e_nao_avanca(logado: TestClient, banco, monkeypatch):
    _cliente(logado, CNPJ_VALIDO, "Padaria Pão Bom")
    _salvar(logado)
    imap = ImapFalso({1: mensagem("um", [("n1.xml", nfe(1, CNPJ_VALIDO, CLIENTE_DO_CLIENTE))])})
    monkeypatch.setattr(servico, "gravar_leitura", lambda *a, **k: 1 / 0)
    r = _verificar(logado, monkeypatch, imap)
    assert r["ok"] is False and "inesperado" in r["erro"] and imap.saiu
    assert _caixa(banco).ultimo_uid is None


def test_senha_ilegivel_pede_para_digitar_de_novo(logado: TestClient, banco, monkeypatch):
    _salvar(logado)
    monkeypatch.setenv("TOLARIS_SECRET_KEY", "outra-chave-bem-diferente-com-mais-de-32-caracteres")
    get_settings.cache_clear()
    try:
        r = servico.verificar(banco, _caixa(banco))  # a sessão antiga cai junto com a chave; o serviço é chamado direto
    finally:
        monkeypatch.undo()
        get_settings.cache_clear()
    assert r["ok"] is False and "Digite a senha de novo" in r["erro"]


def test_anexos_perigosos_ou_irrelevantes_sao_ignorados(logado: TestClient, banco, monkeypatch):
    a = _cliente(logado, CNPJ_VALIDO, "Padaria Pão Bom")
    _salvar(logado)
    xml_malicioso = b'<?xml version="1.0"?><!DOCTYPE x [<!ENTITY e SYSTEM "file:///etc/passwd">]><emit><CNPJ>' + CNPJ_VALIDO.encode() + b"</CNPJ></emit>"
    imap = ImapFalso({
        1: mensagem("xxe", [("x.xml", xml_malicioso)]),
        2: mensagem("zip quebrado", [("z.zip", b"isto nao e zip")]),
        3: mensagem("script", [("a.exe", b"MZ"), ("b.html", b"<script>")]),
    })
    r = _verificar(logado, monkeypatch, imap)
    assert r["ok"] and r["importados"] == 0 and _notas(banco, a) == 0


def test_identifica_cnpj_nos_arquivos():
    assert servico.cnpjs_do_arquivo("n.xml", nfe(1, FORNECEDOR, CLIENTE_DO_CLIENTE)) == {FORNECEDOR, CLIENTE_DO_CLIENTE}
    assert servico.cnpjs_do_arquivo("s.txt", sped(CNPJ_VALIDO)) == {CNPJ_VALIDO}
    assert servico.cnpjs_do_arquivo("s.txt", b"qualquer coisa") == set()
    com_prefixo = b"<nfe:emit><nfe:CNPJ>11222333000181</nfe:CNPJ></nfe:emit>"
    assert servico.cnpjs_do_arquivo("p.xml", com_prefixo) == {CNPJ_VALIDO}


# --- Rotina automática ---------------------------------------------------------------------------------------------
def test_rotina_respeita_intervalo_e_caixa_desligada(logado: TestClient, banco, monkeypatch):
    _cliente(logado, CNPJ_VALIDO, "Padaria Pão Bom")
    _salvar(logado)
    monkeypatch.setattr(servico, "abrir_conexao", lambda h, p: ImapFalso({}))
    fabrica = sessionmaker(bind=banco.get_bind(), expire_on_commit=False)
    assert servico.verificar_vencidas(fabrica) == 1  # nunca verificada
    assert servico.verificar_vencidas(fabrica) == 0  # acabou de verificar
    caixa = _caixa(banco)
    caixa.ultima_verificacao_em = agora() - timedelta(minutes=get_settings().imap_intervalo_minutos + 1)
    banco.commit()
    assert servico.verificar_vencidas(fabrica) == 1
    caixa = _caixa(banco)
    caixa.ultima_verificacao_em, caixa.ativo = None, False
    banco.commit()
    assert servico.verificar_vencidas(fabrica) == 0


def test_automatico_so_liga_em_producao_ou_quando_pedido(monkeypatch):
    for chave, valor, esperado in (("TOLARIS_AMBIENTE", "desenvolvimento", False), ("TOLARIS_AMBIENTE", "producao", True)):
        monkeypatch.setenv(chave, valor)
        get_settings.cache_clear()
        assert servico.automatico_ligado() is esperado
    monkeypatch.setenv("TOLARIS_IMAP_AUTOMATICO", "false")
    get_settings.cache_clear()
    assert servico.automatico_ligado() is False
    monkeypatch.undo()
    monkeypatch.setenv("TOLARIS_IMAP_AUTOMATICO", "true")
    get_settings.cache_clear()
    assert servico.automatico_ligado() is True
    monkeypatch.undo()
    get_settings.cache_clear()


def test_excluir_escritorio_nao_deixa_caixa(logado: TestClient):
    _salvar(logado)
    cadastrar(logado, email="outra@escritorio.com.br", escritorio="Outro Escritório")
    assert logado.get("/api/escritorio/caixa-email").json()["configurada"] is False  # não enxerga a do outro


# --- Conexão real (TLS) com um servidor IMAP local ------------------------------------------------------------------
def _certificado(tmp_path, nome: str):
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import NameOID

    chave = ec.generate_private_key(ec.SECP256R1())
    assunto = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, nome)])
    cert = (
        x509.CertificateBuilder().subject_name(assunto).issuer_name(assunto).public_key(chave.public_key())
        .serial_number(x509.random_serial_number()).not_valid_before(agora() - timedelta(days=1))
        .not_valid_after(agora() + timedelta(days=1))
        .add_extension(x509.SubjectAlternativeName([x509.DNSName(nome)]), critical=False)
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(chave, hashes.SHA256())
    )
    pem = tmp_path / "cert.pem"
    pem.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    chv = tmp_path / "chave.pem"
    chv.write_bytes(chave.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    return pem, chv


def test_conexao_tls_vai_no_ip_validado_e_confere_o_certificado(tmp_path, monkeypatch):
    import ssl
    import threading

    nome = "imap.exemplo.com.br"
    pem, chv = _certificado(tmp_path, nome)
    contexto_servidor = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    contexto_servidor.load_cert_chain(pem, chv)
    escuta = socket.socket()
    escuta.bind(("127.0.0.1", 0))
    escuta.listen(1)
    porta = escuta.getsockname()[1]

    def servidor():
        conexao, _ = escuta.accept()
        with contexto_servidor.wrap_socket(conexao, server_side=True) as tls:
            tls.sendall(b"* OK [CAPABILITY IMAP4rev1] pronto\r\n")
            dados = tls.recv(1024)  # "<tag> LOGIN usuario senha"
            tag = dados.split()[0]
            tls.sendall(b"* CAPABILITY IMAP4rev1\r\n" + tag + b" OK LOGIN completo\r\n")
            tls.recv(1024)
            tls.sendall(b"* BYE\r\n")

    threading.Thread(target=servidor, daemon=True).start()
    monkeypatch.setenv("TOLARIS_IMAP_PERMITIR_REDE_PRIVADA", "true")
    get_settings.cache_clear()
    monkeypatch.setattr(socket, "getaddrinfo", lambda host, p, *a, **kw: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", p))])
    original = ssl.create_default_context
    monkeypatch.setattr(servico.ssl, "create_default_context", lambda: original(cafile=str(pem)))
    try:
        imap = servico.abrir_conexao(nome, porta)
        imap.login("u", "s")
        imap.logout()
    finally:
        get_settings.cache_clear()
        escuta.close()


def test_conexao_tls_recusa_certificado_de_outro_nome(tmp_path, monkeypatch):
    import ssl
    import threading

    pem, chv = _certificado(tmp_path, "outro-nome.exemplo.com")
    contexto_servidor = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    contexto_servidor.load_cert_chain(pem, chv)
    escuta = socket.socket()
    escuta.bind(("127.0.0.1", 0))
    escuta.listen(1)

    def servidor():
        try:
            conexao, _ = escuta.accept()
            contexto_servidor.wrap_socket(conexao, server_side=True)
        except OSError:
            pass

    threading.Thread(target=servidor, daemon=True).start()
    monkeypatch.setenv("TOLARIS_IMAP_PERMITIR_REDE_PRIVADA", "true")
    get_settings.cache_clear()
    monkeypatch.setattr(socket, "getaddrinfo", lambda host, p, *a, **kw: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", p))])
    original = ssl.create_default_context
    monkeypatch.setattr(servico.ssl, "create_default_context", lambda: original(cafile=str(pem)))
    try:
        with pytest.raises(servico.ErroCaixa, match="certificado"):
            servico.abrir_conexao("imap.exemplo.com.br", escuta.getsockname()[1])
    finally:
        get_settings.cache_clear()
        escuta.close()
