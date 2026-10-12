"""Envio de e-mail: console (testes), arquivo (desenvolvimento), SMTP ou Resend (API HTTP).

O backend vem de ``TOLARIS_EMAIL_BACKEND``. No modo console nada sai do servidor:
as mensagens ficam em ``CAIXA_SAIDA`` e no log, o que permite testar os fluxos sem provedor.
"""

from __future__ import annotations

import base64
import json
import logging
import smtplib
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from email.message import EmailMessage
from email.utils import formataddr, parseaddr
from html import escape

import httpx

from .config import get_settings

log = logging.getLogger("tolaris.email")

CAIXA_SAIDA: deque[Mensagem] = deque(maxlen=100)


class ErroEnvio(Exception):
    pass


@dataclass
class Anexo:
    nome: str
    conteudo: bytes
    mime: str = "application/pdf"


@dataclass
class Mensagem:
    para: list[str]
    assunto: str
    texto: str
    html: str
    nome_remetente: str | None = None
    """Nome exibido (ex.: o escritório). O endereço é sempre o remetente configurado."""
    responder_para: str | None = None
    anexos: list[Anexo] = field(default_factory=list)


def _remetente(msg: Mensagem) -> str:
    nome_cfg, endereco = parseaddr(get_settings().email_remetente)
    nome = f"{msg.nome_remetente} via Tolaris" if msg.nome_remetente else (nome_cfg or "Tolaris Contábil")
    return formataddr((nome, endereco))


def _smtp(msg: Mensagem) -> None:
    cfg = get_settings()
    em = EmailMessage()
    em["From"] = _remetente(msg)
    em["To"] = ", ".join(msg.para)
    em["Subject"] = msg.assunto
    if msg.responder_para:
        em["Reply-To"] = msg.responder_para
    em.set_content(msg.texto)
    em.add_alternative(msg.html, subtype="html")
    for a in msg.anexos:
        tipo, sub = a.mime.split("/", 1)
        em.add_attachment(a.conteudo, maintype=tipo, subtype=sub, filename=a.nome)
    try:
        with smtplib.SMTP(cfg.smtp_host, cfg.smtp_porta, timeout=20) as s:
            if cfg.smtp_tls:
                s.starttls()
            if cfg.smtp_usuario:
                s.login(cfg.smtp_usuario, cfg.smtp_senha)
            s.send_message(em)
    except (smtplib.SMTPException, OSError) as erro:
        raise ErroEnvio(f"Falha no SMTP: {erro}") from erro


def _resend(msg: Mensagem) -> None:
    cfg = get_settings()
    corpo = {
        "from": _remetente(msg),
        "to": msg.para,
        "subject": msg.assunto,
        "text": msg.texto,
        "html": msg.html,
        "attachments": [{"filename": a.nome, "content": base64.b64encode(a.conteudo).decode()} for a in msg.anexos],
    }
    if msg.responder_para:
        corpo["reply_to"] = msg.responder_para
    try:
        resp = httpx.post(
            "https://api.resend.com/emails",
            json=corpo,
            headers={"Authorization": f"Bearer {cfg.resend_api_key}"},
            timeout=20,
        )
    except httpx.HTTPError as erro:
        raise ErroEnvio(f"Falha ao contatar o Resend: {erro}") from erro
    if resp.status_code >= 400:
        raise ErroEnvio(f"Resend respondeu {resp.status_code}: {resp.text[:200]}")


def _arquivo(msg: Mensagem) -> None:
    """Grava cada mensagem como JSON (e os anexos ao lado) em TOLARIS_EMAIL_PASTA."""
    pasta = Path(get_settings().email_pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    base = pasta / datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    anexos = []
    for i, a in enumerate(msg.anexos):
        caminho = base.with_name(f"{base.name}-{i}-{Path(a.nome).name}")
        caminho.write_bytes(a.conteudo)
        anexos.append(caminho.name)
    dados = {"para": msg.para, "assunto": msg.assunto, "remetente": _remetente(msg), "responder_para": msg.responder_para,
             "texto": msg.texto, "html": msg.html, "anexos": anexos}
    base.with_suffix(".json").write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")


def enviar(msg: Mensagem) -> None:
    backend = get_settings().email_backend
    if backend == "arquivo":
        _arquivo(msg)
    elif backend == "smtp":
        _smtp(msg)
    elif backend == "resend":
        _resend(msg)
    elif backend == "console":
        CAIXA_SAIDA.append(msg)
        log.info("E-mail (console) para %s: %s\n%s", msg.para, msg.assunto, msg.texto)
    else:
        raise ErroEnvio(f"Backend de e-mail desconhecido: {backend}")


def montar_html(titulo: str, paragrafos: list[str], cor: str = "#1F3A5F", botao: tuple[str, str] | None = None,
                rodape: str = "Tolaris Contábil") -> str:
    """HTML simples e compatível com clientes de e-mail (tabelas e estilos inline)."""
    corpo = "".join(f'<p style="margin:0 0 14px;line-height:1.5">{escape(p)}</p>' for p in paragrafos)
    if botao:
        texto, url = botao
        corpo += (
            f'<p style="margin:22px 0"><a href="{escape(url, quote=True)}" '
            f'style="background:{escape(cor)};color:#ffffff;text-decoration:none;padding:12px 20px;'
            f'border-radius:6px;font-weight:600;display:inline-block">{escape(texto)}</a></p>'
            f'<p style="margin:0 0 14px;font-size:12px;color:#5B6775">Se o botão não funcionar, copie o endereço: '
            f'{escape(url)}</p>'
        )
    return (
        '<!doctype html><html><body style="margin:0;background:#F5F7F9;font-family:Helvetica,Arial,sans-serif;color:#1D2733">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr><td align="center" style="padding:24px">'
        '<table role="presentation" width="560" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:8px">'
        f'<tr><td style="background:{escape(cor)};height:6px;border-radius:8px 8px 0 0"></td></tr>'
        f'<tr><td style="padding:28px"><h1 style="font-size:20px;margin:0 0 18px">{escape(titulo)}</h1>{corpo}</td></tr>'
        f'<tr><td style="padding:0 28px 24px;font-size:12px;color:#5B6775">{escape(rodape)}</td></tr>'
        "</table></td></tr></table></body></html>"
    )


def enviar_sem_falhar(msg: Mensagem) -> None:
    """Para tarefas em segundo plano: registra a falha em vez de derrubar o processo."""
    try:
        enviar(msg)
    except ErroEnvio:
        log.exception("Falha ao enviar e-mail para %s (%s)", msg.para, msg.assunto)
