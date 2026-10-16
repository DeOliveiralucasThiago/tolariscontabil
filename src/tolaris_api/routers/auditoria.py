"""Registro de atividades do escritório (só administradores)."""

from __future__ import annotations

import csv
import io
from datetime import date, datetime, time, timedelta, timezone

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from ..acesso import agora
from ..auditoria import ROTULOS
from ..config import get_settings
from ..db import get_db
from ..models import RegistroAuditoria, Usuario
from ..schemas import AuditoriaItem, AuditoriaPagina
from ..seguranca import somente_admin

router = APIRouter(prefix="/escritorio/auditoria", tags=["auditoria"])

LIMITE_CSV = 10000


def _item(r: RegistroAuditoria) -> AuditoriaItem:
    return AuditoriaItem(
        id=r.id, quando=r.criado_em, usuario=r.usuario_nome, acao=r.acao, rotulo=ROTULOS.get(r.acao, r.acao),
        entidade=r.entidade, entidade_id=r.entidade_id, detalhe=r.detalhe, ip=r.ip,
    )


def _consulta(admin: Usuario, acao: str | None, usuario_id: int | None, desde: date | None, ate: date | None):
    c = select(RegistroAuditoria).where(RegistroAuditoria.escritorio_id == admin.escritorio_id)
    if acao:
        c = c.where(RegistroAuditoria.acao == acao)
    if usuario_id:
        c = c.where(RegistroAuditoria.usuario_id == usuario_id)
    if desde:
        c = c.where(RegistroAuditoria.criado_em >= datetime.combine(desde, time.min, tzinfo=timezone.utc))
    if ate:
        c = c.where(RegistroAuditoria.criado_em < datetime.combine(ate + timedelta(days=1), time.min, tzinfo=timezone.utc))
    return c


def _limpar_antigos(db: Session, escritorio_id: int) -> None:
    corte = agora() - timedelta(days=30 * get_settings().auditoria_retencao_meses)
    db.execute(delete(RegistroAuditoria).where(RegistroAuditoria.escritorio_id == escritorio_id, RegistroAuditoria.criado_em < corte))
    db.commit()


@router.get("", response_model=AuditoriaPagina)
def listar(
    acao: str | None = Query(default=None, max_length=60),
    usuario_id: int | None = None,
    desde: date | None = None,
    ate: date | None = None,
    limite: int = Query(default=50, ge=1, le=200),
    deslocamento: int = Query(default=0, ge=0),
    admin: Usuario = Depends(somente_admin),
    db: Session = Depends(get_db),
) -> AuditoriaPagina:
    _limpar_antigos(db, admin.escritorio_id)
    base = _consulta(admin, acao, usuario_id, desde, ate)
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    linhas = db.scalars(base.order_by(RegistroAuditoria.criado_em.desc(), RegistroAuditoria.id.desc()).limit(limite).offset(deslocamento))
    return AuditoriaPagina(
        total=total,
        itens=[_item(r) for r in linhas],
        acoes=[{"codigo": k, "rotulo": v} for k, v in ROTULOS.items()],
        retencao_meses=get_settings().auditoria_retencao_meses,
    )


def _celula(v: object) -> str:
    """Evita que o Excel execute fórmula vinda de texto digitado por alguém (=, +, -, @ no começo)."""
    texto = "" if v is None else str(v)
    return "'" + texto if texto[:1] in ("=", "+", "-", "@", "\t", "\r") else texto


@router.get("/exportar.csv")
def exportar(
    acao: str | None = Query(default=None, max_length=60),
    usuario_id: int | None = None,
    desde: date | None = None,
    ate: date | None = None,
    admin: Usuario = Depends(somente_admin),
    db: Session = Depends(get_db),
) -> Response:
    base = _consulta(admin, acao, usuario_id, desde, ate)
    saida = io.StringIO()
    escritor = csv.writer(saida, delimiter=";", lineterminator="\r\n")
    escritor.writerow(["Data e hora (UTC)", "Usuário", "Ação", "Código", "Entidade", "ID", "Detalhe", "IP"])
    for r in db.scalars(base.order_by(RegistroAuditoria.criado_em.desc(), RegistroAuditoria.id.desc()).limit(LIMITE_CSV)):
        escritor.writerow([
            r.criado_em.strftime("%Y-%m-%d %H:%M:%S"), _celula(r.usuario_nome), ROTULOS.get(r.acao, r.acao), r.acao,
            r.entidade or "", r.entidade_id or "", _celula(r.detalhe and str(r.detalhe)), r.ip or "",
        ])
    return Response(
        ("﻿" + saida.getvalue()).encode("utf-8"), media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="registro-de-atividades.csv"'},
    )
