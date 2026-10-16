"""Caixa de entrada de notas por e-mail (IMAP).

O escritório aponta uma caixa de e-mail; os anexos XML/ZIP/SPED que chegam nela são lidos, o cliente é
identificado pelo CNPJ dentro do arquivo (emitente/destinatário da nota ou registro 0000 do SPED) e as notas
entram no movimento fiscal dele, sem duplicar.

Cuidados: a caixa é aberta só para leitura (nada é marcado como lido nem apagado); o progresso fica no UID da
última mensagem; o servidor informado é validado contra SSRF e a conexão é sempre TLS.
"""

from __future__ import annotations

import imaplib
import io
import ipaddress
import logging
import re
import socket
import ssl
import threading
import zipfile
from datetime import timedelta
from email import message_from_bytes, policy
from email.message import EmailMessage
from typing import Any, Callable

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from .acesso import _aware, agora
from .config import get_settings
from .importacao import MAX_ARQUIVOS_ZIP, MAX_DESCOMPACTADO, MAX_POR_ARQUIVO, ler_arquivos
from .importar import gravar_leitura
from .models import CaixaEmail, Cliente
from .segredos import SegredoIlegivel, decifrar

log = logging.getLogger("tolaris.caixa_email")

MAX_MENSAGENS_POR_VEZ = 50
MAX_BYTES_MENSAGEM = 40 * 1024 * 1024
EXTENSOES = (".xml", ".zip", ".txt")
MESES_IMAP = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
_HOST = re.compile(r"^(?=.{1,253}$)([A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?)(\.[A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?)*$")


class ErroCaixa(Exception):
    """Falha que o escritório precisa ver (servidor inválido, senha errada...)."""


# --- Destino seguro -----------------------------------------------------------------------------
def validar_destino(host: str, porta: int) -> str:
    """Confere host e porta e devolve o IP a ser usado na conexão (assim o DNS não muda entre a checagem e o uso)."""
    cfg = get_settings()
    host = host.strip().rstrip(".")
    if not _HOST.match(host):
        raise ErroCaixa("Servidor IMAP inválido")
    if not cfg.imap_permitir_rede_privada and porta != 993:
        raise ErroCaixa("Use a porta 993 (IMAP com SSL).")
    try:
        enderecos = {i[4][0] for i in socket.getaddrinfo(host, porta, type=socket.SOCK_STREAM)}
    except socket.gaierror:
        raise ErroCaixa("Não encontramos esse servidor IMAP. Confira o endereço.") from None
    if not enderecos:
        raise ErroCaixa("Não encontramos esse servidor IMAP. Confira o endereço.")
    for ip in sorted(enderecos):
        if not cfg.imap_permitir_rede_privada and not ipaddress.ip_address(ip.split("%")[0]).is_global:
            raise ErroCaixa("Esse endereço aponta para uma rede interna e não é aceito.")
    return sorted(enderecos)[0]


class _ImapNoIp(imaplib.IMAP4_SSL):
    """IMAP com TLS que conecta no IP já validado, mas confere o certificado pelo nome do servidor."""

    def __init__(self, host: str, ip: str, porta: int, timeout: float) -> None:
        self._ip = ip
        super().__init__(host, porta, ssl_context=ssl.create_default_context(), timeout=timeout)

    def _create_socket(self, timeout: float | None) -> ssl.SSLSocket:  # type: ignore[override]
        sock = socket.create_connection((self._ip, self.port), timeout)
        return self.ssl_context.wrap_socket(sock, server_hostname=self.host)


def abrir_conexao(host: str, porta: int) -> Any:
    ip = validar_destino(host, porta)
    try:
        return _ImapNoIp(host.strip().rstrip("."), ip, porta, get_settings().imap_timeout_segundos)
    except ssl.SSLError:
        raise ErroCaixa("Falha na conexão segura (certificado do servidor não confere).") from None
    except OSError:
        raise ErroCaixa("Não foi possível conectar ao servidor IMAP (porta 993).") from None


# --- Anexos ---------------------------------------------------------------------------------------
def anexos_da_mensagem(bruto: bytes) -> tuple[str, list[tuple[str, bytes]]]:
    """(assunto, [(nome, conteúdo)]) dos anexos .xml/.zip/.txt de uma mensagem."""
    msg = message_from_bytes(bruto, policy=policy.default)
    assunto = str(msg.get("Subject", "") or "")[:120]
    achados: list[tuple[str, bytes]] = []
    if not isinstance(msg, EmailMessage):  # pragma: no cover - a política default sempre devolve EmailMessage
        return assunto, achados
    for n, parte in enumerate(msg.walk(), start=1):
        if parte.is_multipart():
            continue
        nome = (parte.get_filename() or "").strip()
        tipo = parte.get_content_type()
        if not nome and tipo in ("application/xml", "text/xml"):
            nome = f"anexo{n}.xml"
        if not nome.lower().endswith(EXTENSOES):
            continue
        dados = parte.get_payload(decode=True) or b""
        if 0 < len(dados) <= MAX_POR_ARQUIVO:
            achados.append((nome.replace("/", "_").replace("\\", "_")[:150], dados))
    return assunto, achados


def expandir(anexos: list[tuple[str, bytes]]) -> list[tuple[str, bytes]]:
    """Abre os ZIP (um nível) e devolve só arquivos .xml/.txt, respeitando os limites da importação."""
    saida: list[tuple[str, bytes]] = []
    for nome, dados in anexos:
        if not nome.lower().endswith(".zip"):
            saida.append((nome, dados))
            continue
        try:
            with zipfile.ZipFile(io.BytesIO(dados)) as z:
                membros = [m for m in z.infolist() if not m.is_dir()]
                if len(membros) > MAX_ARQUIVOS_ZIP or sum(m.file_size for m in membros) > MAX_DESCOMPACTADO:
                    continue
                for m in membros:
                    if m.file_size <= MAX_POR_ARQUIVO and m.filename.lower().endswith((".xml", ".txt")):
                        with z.open(m) as f:
                            saida.append((f"{nome}/{m.filename}", f.read(MAX_POR_ARQUIVO + 1)))
        except zipfile.BadZipFile:
            continue
    return saida


_EMIT = re.compile(rb"<(?:\w+:)?emit>\s*<(?:\w+:)?CNPJ>(\d{14})<")
_DEST = re.compile(rb"<(?:\w+:)?dest>\s*<(?:\w+:)?CNPJ>(\d{14})<")


def cnpjs_do_arquivo(nome: str, dados: bytes) -> set[str]:
    """CNPJs que identificam de quem é o arquivo: emitente e destinatário da NF-e, ou o dono do SPED."""
    if nome.lower().endswith(".txt"):
        for linha in dados[:4000].decode("latin-1").splitlines():
            campos = linha.split("|")
            if len(campos) > 7 and campos[1] == "0000":
                return {campos[7]} if re.fullmatch(r"\d{14}", campos[7]) else set()
        return set()
    return {m.group(1).decode() for rx in (_EMIT, _DEST) if (m := rx.search(dados[:200_000]))}


# --- Verificação -----------------------------------------------------------------------------------
def _data_imap(d) -> str:  # noqa: ANN001
    return f"{d.day:02d}-{MESES_IMAP[d.month - 1]}-{d.year}"


def _tamanho(resposta: list) -> int:
    texto = b" ".join(x if isinstance(x, bytes) else x[0] for x in resposta if x)
    m = re.search(rb"RFC822\.SIZE (\d+)", texto)
    return int(m.group(1)) if m else 0


def _corpo(resposta: list) -> bytes | None:
    return next((x[1] for x in resposta if isinstance(x, tuple)), None)


def _uids(imap: Any, caixa: CaixaEmail, validade: int | None) -> list[int]:
    if caixa.ultimo_uid is not None and caixa.uid_validade == validade:
        tipo, dados = imap.uid("SEARCH", None, "UID", f"{caixa.ultimo_uid + 1}:*")
        achados = [int(x) for x in (dados[0] or b"").split()]
        achados = [u for u in achados if u > caixa.ultimo_uid]  # "N:*" sempre devolve a última, mesmo já lida
    else:
        desde = agora() - timedelta(days=get_settings().imap_dias_iniciais)
        tipo, dados = imap.uid("SEARCH", None, "SINCE", _data_imap(desde))
        achados = [int(x) for x in (dados[0] or b"").split()]
    if tipo != "OK":
        raise ErroCaixa("O servidor recusou a busca de mensagens.")
    return sorted(achados)


def verificar(db: Session, caixa: CaixaEmail, abrir: Callable[[str, int], Any] | None = None) -> dict[str, Any]:
    """Lê as mensagens novas, importa as notas e guarda o resultado. Nunca levanta: o erro vai no resultado."""
    resultado: dict[str, Any] = {
        "em": agora().isoformat(), "ok": False, "erro": None, "mensagens": 0, "com_anexos": 0,
        "importados": 0, "duplicados": 0, "sem_cliente": [], "por_cliente": [],
    }
    imap = None
    try:
        try:
            senha = decifrar(caixa.senha_cifrada)
        except SegredoIlegivel as erro:
            raise ErroCaixa(str(erro)) from None
        imap = (abrir or abrir_conexao)(caixa.host, caixa.porta)
        try:
            imap.login(caixa.usuario, senha)
        except imaplib.IMAP4.error:
            raise ErroCaixa("Usuário ou senha recusados pelo servidor. Em Gmail/Outlook use uma senha de aplicativo.") from None
        tipo, _ = imap.select(f'"{caixa.pasta}"', readonly=True)
        if tipo != "OK":
            raise ErroCaixa(f"Pasta “{caixa.pasta}” não encontrada na caixa de e-mail.")
        _, v = imap.response("UIDVALIDITY")
        validade = int(v[0]) if v and v[0] else None

        clientes = {
            c.cnpj: c for c in db.scalars(select(Cliente).where(Cliente.escritorio_id == caixa.escritorio_id, Cliente.cnpj.is_not(None)))
        }
        por_cliente: dict[int, dict[str, Any]] = {}
        uids = _uids(imap, caixa, validade)
        ultimo = caixa.ultimo_uid if caixa.uid_validade == validade else None
        for uid in uids[:MAX_MENSAGENS_POR_VEZ]:
            resultado["mensagens"] += 1
            ultimo = uid
            _, info = imap.uid("FETCH", str(uid), "(RFC822.SIZE)")
            if _tamanho(info) > MAX_BYTES_MENSAGEM:
                resultado["sem_cliente"].append("(mensagem grande demais)")
                continue
            _, dados = imap.uid("FETCH", str(uid), "(BODY.PEEK[])")
            bruto = _corpo(dados)
            if not bruto:
                continue
            assunto, anexos = anexos_da_mensagem(bruto)
            if not anexos:
                continue
            resultado["com_anexos"] += 1
            grupos: dict[str, list[tuple[str, bytes]]] = {}
            sem_dono = True
            for nome, conteudo in expandir(anexos):
                for cnpj in cnpjs_do_arquivo(nome, conteudo) & clientes.keys():
                    grupos.setdefault(cnpj, []).append((nome, conteudo))
                    sem_dono = False
            if sem_dono and len(resultado["sem_cliente"]) < 10:
                resultado["sem_cliente"].append(assunto or "(sem assunto)")
            for cnpj, arquivos in grupos.items():
                cliente = clientes[cnpj]
                saida = gravar_leitura(db, caixa.escritorio_id, cliente, ler_arquivos(arquivos, cnpj))
                item = por_cliente.setdefault(cliente.id, {"cliente_id": cliente.id, "cliente": cliente.razao_social, "importados": 0})
                item["importados"] += saida.importados
                resultado["importados"] += saida.importados
                resultado["duplicados"] += saida.duplicados
        resultado["por_cliente"] = list(por_cliente.values())
        caixa.ultimo_uid, caixa.uid_validade = ultimo, validade
        resultado["ok"] = True
    except ErroCaixa as erro:
        resultado["erro"] = str(erro)
    except (imaplib.IMAP4.error, OSError, ssl.SSLError) as erro:
        log.warning("Falha ao ler a caixa %s: %s", caixa.id, type(erro).__name__)
        resultado["erro"] = "Falha de comunicação com o servidor de e-mail. Tente de novo em instantes."
    except Exception:  # noqa: BLE001 - uma caixa com problema não derruba as demais
        log.exception("Erro inesperado ao ler a caixa %s", caixa.id)
        resultado["erro"] = "Erro inesperado ao processar a caixa de e-mail."
    finally:
        if imap is not None:
            try:
                imap.logout()
            except Exception:  # noqa: BLE001
                pass
    if resultado["erro"]:
        db.rollback()  # descarta o que ficou pela metade; o progresso (UID) só avança em verificação completa
    caixa.ultima_verificacao_em = agora()
    caixa.ultimo_resultado = resultado
    db.commit()
    return resultado


# --- Verificação periódica -----------------------------------------------------------------------------
def automatico_ligado() -> bool:
    cfg = get_settings()
    ligado = cfg.imap_automatico if cfg.imap_automatico is not None else cfg.ambiente == "producao"
    return bool(ligado and cfg.imap_intervalo_minutos > 0)


def verificar_vencidas(fabrica: sessionmaker[Session]) -> int:
    """Uma rodada: verifica as caixas ativas cuja última leitura passou do intervalo. Devolve quantas leu."""
    limite = agora() - timedelta(minutes=get_settings().imap_intervalo_minutos)
    with fabrica() as db:
        ids = [
            c.id for c in db.scalars(select(CaixaEmail).where(CaixaEmail.ativo.is_(True)))
            if c.ultima_verificacao_em is None or _aware(c.ultima_verificacao_em) <= limite
        ]
    for caixa_id in ids:
        with fabrica() as db:
            caixa = db.get(CaixaEmail, caixa_id)
            if caixa is not None and caixa.ativo:
                verificar(db, caixa)
    return len(ids)


def iniciar_rotina(fabrica: sessionmaker[Session]) -> threading.Event:
    """Dispara a rotina em segundo plano; o Event devolvido a encerra."""
    parar = threading.Event()

    def laco() -> None:
        while not parar.wait(60):
            try:
                verificar_vencidas(fabrica)
            except Exception:  # noqa: BLE001
                log.exception("Falha na rodada de leitura das caixas de e-mail")

    threading.Thread(target=laco, name="caixa-email", daemon=True).start()
    return parar
