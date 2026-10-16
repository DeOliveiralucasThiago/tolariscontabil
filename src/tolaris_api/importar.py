"""Gravação das notas lidas (XML e SPED) no cliente: usada pela importação interna, pelo link de envio do cliente
e pela caixa de e-mail. Notas repetidas são ignoradas e notas antigas, sem itens, são completadas."""

from __future__ import annotations

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import get_settings
from .importacao import ResultadoLeitura
from .models import Cliente, DocumentoFiscal, ItemFiscal
from .schemas import ImportacaoSaida


async def ler_uploads(arquivos: list[UploadFile]) -> list[tuple[str, bytes]]:
    """Lê os arquivos enviados respeitando o limite de tamanho total (413 se passar)."""
    mb = get_settings().importacao_max_mb
    limite = mb * 1024 * 1024
    lidos, total = [], 0
    for arq in arquivos:
        conteudo = await arq.read(limite - total + 1)
        total += len(conteudo)
        if total > limite:
            raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, f"Envio acima de {mb} MB; divida em partes")
        lidos.append((arq.filename or "arquivo", conteudo))
    return lidos


def gravar_leitura(db: Session, escritorio_id: int, cliente: Cliente, leitura: ResultadoLeitura) -> ImportacaoSaida:
    existentes = dict(db.execute(
        select(DocumentoFiscal.chave, DocumentoFiscal.id).where(DocumentoFiscal.cliente_id == cliente.id)
    ).all())
    com_itens = set(db.scalars(select(ItemFiscal.documento_id).where(ItemFiscal.cliente_id == cliente.id).distinct()))
    novos, duplicados, atualizados, competencias = 0, 0, 0, set()

    def itens_de(doc, **extra):
        return [ItemFiscal(
            escritorio_id=escritorio_id, cliente_id=cliente.id, **extra,
            tipo=doc.tipo, competencia=doc.competencia, ncm=i.ncm, cfop=i.cfop, cst_icms=i.cst_icms,
            cst_pis=i.cst_pis, cest=i.cest, descricao=i.descricao, valor_centavos=i.valor,
            quantidade_itens=i.quantidade,
        ) for i in doc.itens]

    for doc in leitura.documentos:
        if doc.chave in existentes:
            duplicados += 1
            id_existente = existentes[doc.chave]
            if doc.itens and id_existente is not None and id_existente not in com_itens:
                # nota importada antes de existir a leitura de itens
                db.add_all(itens_de(doc, documento_id=id_existente))
                com_itens.add(id_existente)
                atualizados += 1
            continue
        existentes[doc.chave] = None  # evita repetir a mesma nota dentro do envio
        db.add(DocumentoFiscal(
            escritorio_id=escritorio_id,
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
            itens=itens_de(doc),
        ))
        novos += 1
        competencias.add(doc.competencia)
    db.commit()
    return ImportacaoSaida(
        importados=novos,
        duplicados=duplicados,
        atualizados=atualizados,
        ignorados=[{"arquivo": a, "motivo": m} for a, m in leitura.ignorados[:50]],
        total_ignorados=len(leitura.ignorados),
        competencias=sorted(competencias),
    )
