"""Exportação de todos os dados de um cliente (LGPD: acesso e portabilidade). Só administradores."""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..acesso import agora
from ..auditoria import auditar
from ..db import get_db
from ..models import (
    CaixaCliente,
    Cliente,
    DocumentoFiscal,
    Envio,
    FinanceiroMensal,
    ItemFiscal,
    PortalCliente,
    RegistroAuditoria,
    Simulacao,
    Usuario,
)
from ..seguranca import somente_admin
from .clientes import obter_cliente

router = APIRouter(tags=["LGPD"])

FORMATO = "tolaris-exportacao-cliente/1"
OCULTAR = {"token_hash", "escritorio_id", "criado_por_id", "enviado_por_id"}
"""Segredos e chaves internas não fazem parte dos dados do titular."""


def _valor(v: Any) -> Any:
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    if isinstance(v, Decimal):
        return float(v)
    return v


def _linha(obj: Any, ocultar: set[str] = frozenset()) -> dict[str, Any]:  # noqa: B006
    return {c.name: _valor(getattr(obj, c.name)) for c in obj.__table__.columns if c.name not in OCULTAR | ocultar}


@router.get("/clientes/{cliente_id}/exportacao")
def exportar(cliente_id: int, admin: Usuario = Depends(somente_admin), db: Session = Depends(get_db)) -> Response:
    cliente: Cliente = obter_cliente(db, admin, cliente_id)
    simulacoes = list(db.scalars(select(Simulacao).where(Simulacao.cliente_id == cliente.id).order_by(Simulacao.id)))
    envios = list(db.scalars(select(Envio).where(Envio.simulacao_id.in_([s.id for s in simulacoes])).order_by(Envio.id))) if simulacoes else []
    itens: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for i in db.scalars(select(ItemFiscal).where(ItemFiscal.cliente_id == cliente.id).order_by(ItemFiscal.id)):
        itens[i.documento_id].append(_linha(i, {"id", "cliente_id", "documento_id"}))
    documentos = [
        {**_linha(d, {"cliente_id"}), "itens": itens.get(d.id, [])}
        for d in db.scalars(select(DocumentoFiscal).where(DocumentoFiscal.cliente_id == cliente.id).order_by(DocumentoFiscal.id))
    ]
    portal = db.scalar(select(PortalCliente).where(PortalCliente.cliente_id == cliente.id))
    caixa = db.scalar(select(CaixaCliente).where(CaixaCliente.cliente_id == cliente.id))
    registros = db.scalars(
        select(RegistroAuditoria)
        .where(RegistroAuditoria.escritorio_id == admin.escritorio_id, RegistroAuditoria.entidade == "cliente", RegistroAuditoria.entidade_id == cliente.id)
        .order_by(RegistroAuditoria.id)
    )
    corpo = {
        "formato": FORMATO,
        "gerado_em": agora().isoformat(),
        "gerado_por": admin.email,
        "aviso": "Contém dados pessoais e fiscais do cliente. Guarde com o mesmo cuidado dado ao sistema e apague a cópia quando não for mais necessária.",
        "cliente": _linha(cliente),
        "simulacoes": [_linha(s, {"cliente_id"}) for s in simulacoes],
        "envios_de_relatorio": [_linha(e) for e in envios],
        "documentos_fiscais": documentos,
        "dados_contabeis": [_linha(f, {"cliente_id"}) for f in db.scalars(select(FinanceiroMensal).where(FinanceiroMensal.cliente_id == cliente.id).order_by(FinanceiroMensal.competencia))],
        "portal_do_cliente": _linha(portal, {"cliente_id"}) if portal else None,
        "link_de_envio_de_notas": _linha(caixa, {"cliente_id"}) if caixa else None,
        "registro_de_atividades": [_linha(r, {"detalhe"}) | {"detalhe": r.detalhe} for r in registros],
    }
    auditar(db, admin.escritorio_id, "cliente_exportado", admin, entidade="cliente", entidade_id=cliente.id,
            detalhe={"documentos": len(documentos), "simulacoes": len(simulacoes)})
    db.commit()
    nome = f"dados-cliente-{cliente.id}-{agora().strftime('%Y%m%d')}.json"
    return Response(
        json.dumps(corpo, ensure_ascii=False, indent=2).encode("utf-8"),
        media_type="application/json; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{nome}"'},
    )
