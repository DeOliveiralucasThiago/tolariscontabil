"""Importação de clientes em lote (planilha com CNPJ) e complemento do cadastro pela consulta de CNPJ."""

from __future__ import annotations

import json
import time

from fastapi import APIRouter, Depends, Form, HTTPException, Response, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import clientes_lote as lote
from .. import planilha as pl
from ..cnpj import CnpjIndisponivel, CnpjNaoEncontrado, formatar_cnpj, sugerir_atividade
from ..auditoria import auditar
from ..db import get_db
from ..importar import ler_uploads
from ..models import Cliente, Usuario
from ..schemas import ClientesAnalise, ClientesImportacaoSaida, ClientesLinha, ClientesPrevia, CompletarSaida
from ..seguranca import usuario_atual
from .cnpj import ConsultaCnpj, get_consulta_cnpj

router = APIRouter(prefix="/clientes-lote", tags=["clientes em lote"])

POR_VEZ = 15
"""Consultas de CNPJ por chamada: a API pública limita a taxa, então o site chama de novo até zerar os pendentes."""
PAUSA_SEGUNDOS = 0.4


async def _tabela(arquivos: list[UploadFile]) -> tuple[list[str], list[list[str]]]:
    if len(arquivos) != 1:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Envie uma planilha por vez")
    nome = arquivos[0].filename or ""
    (_, conteudo), = await ler_uploads(arquivos)
    try:
        return pl.ler_tabela(nome, conteudo)
    except pl.PlanilhaInvalida as erro:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(erro)) from None


def _mapa(texto: str, colunas: int) -> dict[str, int]:
    try:
        bruto = json.loads(texto)
        if not isinstance(bruto, dict):
            raise ValueError
    except ValueError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Mapeamento de colunas inválido") from None
    limpo = {k: v for k, v in bruto.items() if v is not None and k in lote.CAMPOS}
    if "cnpj" not in limpo:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Indique a coluna do CNPJ")
    if any(not isinstance(i, int) or isinstance(i, bool) or not 0 <= i < colunas for i in limpo.values()):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Coluna escolhida fora da planilha")
    if len(set(limpo.values())) != len(limpo):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "A mesma coluna foi escolhida para dois campos")
    return limpo


def _classificar(db: Session, usuario: Usuario, leitura: lote.Leitura) -> tuple[list[lote.LinhaLida], ClientesAnalise]:
    existentes = set(db.scalars(select(Cliente.cnpj).where(Cliente.escritorio_id == usuario.escritorio_id, Cliente.cnpj.is_not(None))))
    vistos: set[str] = set()
    novas: list[lote.LinhaLida] = []
    problemas: list[ClientesLinha] = [
        ClientesLinha(linha=n, cnpj=c, situacao="invalido", motivo=m) for n, c, m in leitura.invalidas
    ]
    contagem = {"existente": 0, "repetido": 0}
    for l in leitura.linhas:
        if l.cnpj in vistos:
            contagem["repetido"] += 1
            problemas.append(ClientesLinha(linha=l.numero, cnpj=formatar_cnpj(l.cnpj), situacao="repetido", motivo="CNPJ repetido na planilha"))
        elif l.cnpj in existentes:
            vistos.add(l.cnpj)
            contagem["existente"] += 1
            problemas.append(ClientesLinha(linha=l.numero, cnpj=formatar_cnpj(l.cnpj), situacao="existente", motivo="Já cadastrado"))
        else:
            vistos.add(l.cnpj)
            novas.append(l)
    problemas.sort(key=lambda p: p.linha)
    analise = ClientesAnalise(
        novos=len(novas), existentes=contagem["existente"], repetidos=contagem["repetido"], invalidos=len(leitura.invalidas),
        avisos=leitura.avisos, problemas=problemas[:30], total_problemas=len(problemas),
    )
    return novas, analise


@router.get("/modelo.csv")
def modelo(_: Usuario = Depends(usuario_atual)) -> Response:
    return Response(
        lote.modelo_csv(), media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="modelo-clientes.csv"'},
    )


@router.post("/previa", response_model=ClientesPrevia)
async def previa(arquivos: list[UploadFile], _: Usuario = Depends(usuario_atual)) -> ClientesPrevia:
    cabecalhos, linhas = await _tabela(arquivos)
    sugestao = pl.sugerir_mapeamento(cabecalhos, lote.SINONIMOS, lote.CAMPOS)
    return ClientesPrevia(cabecalhos=cabecalhos, amostra=linhas[:5], total_linhas=len(linhas), sugestao=sugestao, rotulos=lote.ROTULOS)


@router.post("/analisar", response_model=ClientesAnalise)
async def analisar(
    arquivos: list[UploadFile], mapeamento: str = Form(), usuario: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)
) -> ClientesAnalise:
    """Confere a planilha com o mapeamento escolhido e diz o que seria criado, sem gravar nada."""
    cabecalhos, linhas = await _tabela(arquivos)
    try:
        leitura = lote.ler(linhas, _mapa(mapeamento, len(cabecalhos)))
    except pl.PlanilhaInvalida as erro:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(erro)) from None
    return _classificar(db, usuario, leitura)[1]


@router.post("/importar", response_model=ClientesImportacaoSaida, status_code=status.HTTP_201_CREATED)
async def importar(
    arquivos: list[UploadFile],
    mapeamento: str = Form(),
    status_padrao: str = Form(default="ativo", pattern="^(ativo|prospect|inativo)$"),
    usuario: Usuario = Depends(usuario_atual),
    db: Session = Depends(get_db),
) -> ClientesImportacaoSaida:
    cabecalhos, linhas = await _tabela(arquivos)
    try:
        leitura = lote.ler(linhas, _mapa(mapeamento, len(cabecalhos)))
    except pl.PlanilhaInvalida as erro:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(erro)) from None
    novas, analise = _classificar(db, usuario, leitura)
    if not novas:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Nenhum cliente novo para importar. Confira os CNPJ e se eles já estão cadastrados.")
    pendentes = 0
    for l in novas:
        d = dict(l.dados)
        pendente = "razao_social" not in d or "atividade" not in d
        pendentes += pendente
        db.add(Cliente(
            escritorio_id=usuario.escritorio_id, cnpj=l.cnpj, razao_social=d.pop("razao_social", None) or lote.placeholder(l.cnpj),
            status=d.pop("status", status_padrao), cadastro_pendente=pendente, **d,
        ))
    auditar(db, usuario.escritorio_id, "clientes_importados", usuario, detalhe={"criados": len(novas), "pendentes": pendentes})
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Algum CNPJ foi cadastrado enquanto a importação rodava. Tente de novo.") from None
    return ClientesImportacaoSaida(**analise.model_dump(), criados=len(novas), pendentes=pendentes)


# --- Completar o cadastro pela consulta de CNPJ ---------------------------------------------------
def _pendentes(db: Session, usuario: Usuario):
    return select(Cliente).where(Cliente.escritorio_id == usuario.escritorio_id, Cliente.cadastro_pendente.is_(True))


@router.get("/pendentes")
def contar_pendentes(usuario: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)) -> dict[str, int]:
    total = db.scalar(select(func.count()).select_from(_pendentes(db, usuario).subquery()))
    return {"pendentes": total or 0}


@router.post("/completar", response_model=CompletarSaida)
def completar(
    usuario: Usuario = Depends(usuario_atual), db: Session = Depends(get_db), consulta: ConsultaCnpj = Depends(get_consulta_cnpj)
) -> CompletarSaida:
    """Consulta até 15 CNPJ pendentes. Só preenche o que está vazio (ou o nome provisório): o que o escritório digitou fica."""
    lote_atual = list(db.scalars(_pendentes(db, usuario).order_by(Cliente.id).limit(POR_VEZ)))
    completados = 0
    nao_encontrados: list[dict[str, str]] = []
    indisponivel = False
    for i, c in enumerate(lote_atual):
        if i:
            time.sleep(PAUSA_SEGUNDOS)
        try:
            dados = consulta(c.cnpj)
        except CnpjNaoEncontrado:
            c.cadastro_pendente = False  # não adianta tentar de novo; o escritório corrige à mão
            nao_encontrados.append({"cnpj": formatar_cnpj(c.cnpj), "motivo": "Não encontrado na Receita Federal"})
            continue
        except CnpjIndisponivel:
            indisponivel = True
            break
        if c.razao_social == lote.placeholder(c.cnpj) and dados.razao_social:
            c.razao_social = dados.razao_social[:250]
        regime = "mei" if dados.opcao_mei else "simples" if dados.opcao_simples else None
        sugerida, _ = sugerir_atividade(dados.cnae_principal)
        for campo, valor in (
            ("nome_fantasia", dados.nome_fantasia), ("cnae_principal", dados.cnae_principal), ("cnae_descricao", dados.cnae_descricao),
            ("municipio", dados.municipio), ("uf", dados.uf), ("email", dados.email), ("telefone", dados.telefone),
            ("atividade", sugerida.value if sugerida else None), ("regime_atual", regime),
            ("cnaes_secundarios", dados.cnaes_secundarios or None),
        ):
            if valor and not getattr(c, campo):
                setattr(c, campo, valor)
        c.cadastro_pendente = False
        completados += 1
    db.commit()
    restantes = db.scalar(select(func.count()).select_from(_pendentes(db, usuario).subquery())) or 0
    return CompletarSaida(completados=completados, nao_encontrados=nao_encontrados, restantes=restantes, indisponivel=indisponivel)
