"""Importação de NF-e (XML) e SPED Fiscal e o movimento mensal do cliente."""

from __future__ import annotations

from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, status
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..importacao import ler_arquivos
from ..models import DocumentoFiscal, Usuario
from ..schemas import ImportacaoSaida, MesMovimento, MovimentoSaida
from ..seguranca import usuario_atual
from .clientes import obter_cliente

router = APIRouter(tags=["importação fiscal"])


@router.post("/clientes/{cliente_id}/importacoes", response_model=ImportacaoSaida, status_code=status.HTTP_201_CREATED)
async def importar(
    cliente_id: int, arquivos: list[UploadFile], usuario: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)
) -> ImportacaoSaida:
    cliente = obter_cliente(db, usuario, cliente_id)
    if not cliente.cnpj:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Cadastre o CNPJ do cliente antes de importar documentos")
    limite = get_settings().importacao_max_mb * 1024 * 1024
    lidos, total = [], 0
    for arq in arquivos:
        conteudo = await arq.read(limite - total + 1)
        total += len(conteudo)
        if total > limite:
            raise HTTPException(
                status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                f"Envio acima de {get_settings().importacao_max_mb} MB; divida em partes",
            )
        lidos.append((arq.filename or "arquivo", conteudo))

    leitura = ler_arquivos(lidos, cliente.cnpj)
    existentes = set(db.scalars(select(DocumentoFiscal.chave).where(DocumentoFiscal.cliente_id == cliente.id)))
    novos, duplicados, competencias = 0, 0, set()
    for doc in leitura.documentos:
        if doc.chave in existentes:
            duplicados += 1
            continue
        existentes.add(doc.chave)
        db.add(DocumentoFiscal(
            escritorio_id=usuario.escritorio_id,
            cliente_id=cliente.id,
            origem=doc.origem,
            chave=doc.chave,
            tipo=doc.tipo,
            modelo=doc.modelo,
            data=doc.data,
            competencia=doc.competencia,
            participante_cnpj=doc.participante_cnpj,
            valor_centavos=doc.valor,
            icms_centavos=doc.icms,
            ipi_centavos=doc.ipi,
            pis_centavos=doc.pis,
            cofins_centavos=doc.cofins,
        ))
        novos += 1
        competencias.add(doc.competencia)
    db.commit()
    return ImportacaoSaida(
        importados=novos,
        duplicados=duplicados,
        ignorados=[{"arquivo": a, "motivo": m} for a, m in leitura.ignorados[:50]],
        total_ignorados=len(leitura.ignorados),
        competencias=sorted(competencias),
    )


@router.get("/clientes/{cliente_id}/movimento", response_model=MovimentoSaida)
def movimento(cliente_id: int, usuario: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)) -> MovimentoSaida:
    cliente = obter_cliente(db, usuario, cliente_id)
    linhas = db.execute(
        select(
            DocumentoFiscal.competencia,
            DocumentoFiscal.tipo,
            func.sum(DocumentoFiscal.valor_centavos),
            func.sum(DocumentoFiscal.icms_centavos),
            func.sum(DocumentoFiscal.ipi_centavos),
            func.sum(DocumentoFiscal.pis_centavos),
            func.sum(DocumentoFiscal.cofins_centavos),
            func.count(),
        )
        .where(DocumentoFiscal.cliente_id == cliente.id)
        .group_by(DocumentoFiscal.competencia, DocumentoFiscal.tipo)
    ).all()
    meses: dict[str, dict] = defaultdict(lambda: {"saidas": 0, "entradas": 0, "icms": 0, "ipi": 0, "pis": 0, "cofins": 0, "documentos": 0})
    for comp, tipo, valor, icms, ipi, pis, cofins, n in linhas:
        m = meses[comp]
        m["saidas" if tipo == "saida" else "entradas"] += valor or 0
        if tipo == "saida":  # tributos destacados nas vendas
            m["icms"] += icms or 0
            m["ipi"] += ipi or 0
            m["pis"] += pis or 0
            m["cofins"] += cofins or 0
        m["documentos"] += n
    ordenados = sorted(meses.items())
    ultimos = ordenados[-12:]
    reais = lambda c: round(c / 100, 2)  # noqa: E731
    return MovimentoSaida(
        meses=[MesMovimento(competencia=k, **{c: (reais(v) if c != "documentos" else v) for c, v in m.items()})
               for k, m in ordenados],
        receita_12m=reais(sum(m["saidas"] for _, m in ultimos)),
        compras_12m=reais(sum(m["entradas"] for _, m in ultimos)),
        meses_12m=len(ultimos),
        documentos=sum(m["documentos"] for m in meses.values()),
    )


@router.delete("/clientes/{cliente_id}/documentos", status_code=status.HTTP_204_NO_CONTENT)
def apagar_documentos(
    cliente_id: int,
    competencia: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}$"),
    usuario: Usuario = Depends(usuario_atual),
    db: Session = Depends(get_db),
) -> None:
    cliente = obter_cliente(db, usuario, cliente_id)
    consulta = delete(DocumentoFiscal).where(DocumentoFiscal.cliente_id == cliente.id)
    if competencia:
        consulta = consulta.where(DocumentoFiscal.competencia == competencia)
    db.execute(consulta)
    db.commit()
