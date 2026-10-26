from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..auditoria import auditar
from ..cnpj import classificar_cnaes
from ..db import get_db
from ..models import Cliente, RegistroAuditoria, Simulacao, Usuario
from ..schemas import ClienteAtualizar, ClienteEntrada, ClienteSaida
from ..seguranca import somente_admin, usuario_atual

router = APIRouter(prefix="/clientes", tags=["clientes"])


def obter_cliente(db: Session, usuario: Usuario, cliente_id: int) -> Cliente:
    cliente = db.get(Cliente, cliente_id)
    if cliente is None or cliente.escritorio_id != usuario.escritorio_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Cliente não encontrado")
    return cliente


def cliente_saida(db: Session, cliente: Cliente) -> ClienteSaida:
    total, ultima = db.execute(
        select(func.count(Simulacao.id), func.max(Simulacao.criado_em)).where(Simulacao.cliente_id == cliente.id)
    ).one()
    saida = ClienteSaida.model_validate(cliente)
    saida.total_simulacoes, saida.ultima_simulacao_em = total, ultima
    return saida


def _cnpj_duplicado() -> HTTPException:
    return HTTPException(status.HTTP_409_CONFLICT, "Já existe um cliente com este CNPJ")


@router.get("", response_model=list[ClienteSaida])
def listar(
    busca: str | None = Query(default=None, max_length=100),
    status_: str | None = Query(default=None, alias="status"),
    usuario: Usuario = Depends(usuario_atual),
    db: Session = Depends(get_db),
) -> list[ClienteSaida]:
    consulta = select(Cliente).where(Cliente.escritorio_id == usuario.escritorio_id)
    if status_:
        consulta = consulta.where(Cliente.status == status_)
    if busca:
        termo = f"%{busca.strip()}%"
        consulta = consulta.where(
            or_(Cliente.razao_social.ilike(termo), Cliente.nome_fantasia.ilike(termo), Cliente.cnpj.ilike(termo))
        )
    clientes = db.scalars(consulta.order_by(Cliente.atualizado_em.desc()).limit(2000)).all()
    return [cliente_saida(db, c) for c in clientes]


@router.get("/{cliente_id}/cnaes")
def cnaes_do_cliente(cliente_id: int, usuario: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)) -> dict:
    c = obter_cliente(db, usuario, cliente_id)
    return classificar_cnaes(c.cnae_principal, c.cnae_descricao, c.cnaes_secundarios, c.atividade)


@router.post("", response_model=ClienteSaida, status_code=status.HTTP_201_CREATED)
def criar(dados: ClienteEntrada, usuario: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)) -> ClienteSaida:
    cliente = Cliente(escritorio_id=usuario.escritorio_id, **dados.model_dump())
    db.add(cliente)
    try:
        db.flush()
        auditar(db, usuario.escritorio_id, "cliente_criado", usuario, entidade="cliente", entidade_id=cliente.id,
                detalhe={"razao_social": cliente.razao_social})
        db.commit()
    except IntegrityError:
        db.rollback()
        raise _cnpj_duplicado() from None
    return cliente_saida(db, cliente)


@router.get("/{cliente_id}", response_model=ClienteSaida)
def detalhar(cliente_id: int, usuario: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)) -> ClienteSaida:
    return cliente_saida(db, obter_cliente(db, usuario, cliente_id))


@router.patch("/{cliente_id}", response_model=ClienteSaida)
def atualizar(
    cliente_id: int, dados: ClienteAtualizar, usuario: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)
) -> ClienteSaida:
    cliente = obter_cliente(db, usuario, cliente_id)
    for campo, valor in dados.model_dump(exclude_unset=True).items():
        if campo in ("razao_social", "status") and valor is None:
            continue
        setattr(cliente, campo, valor)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise _cnpj_duplicado() from None
    return cliente_saida(db, cliente)


@router.delete("/{cliente_id}", status_code=status.HTTP_204_NO_CONTENT)
def excluir(cliente_id: int, usuario: Usuario = Depends(somente_admin), db: Session = Depends(get_db)) -> None:
    """Exclusão definitiva (LGPD): apaga o cliente e tudo que depende dele. O registro de atividades guarda só que a
    exclusão aconteceu; o nome do cliente é retirado dos registros anteriores."""
    cliente = obter_cliente(db, usuario, cliente_id)
    anteriores = db.scalars(
        select(RegistroAuditoria).where(
            RegistroAuditoria.escritorio_id == usuario.escritorio_id,
            RegistroAuditoria.entidade == "cliente",
            RegistroAuditoria.entidade_id == cliente.id,
        )
    )
    for r in anteriores:
        r.detalhe = {k: v for k, v in (r.detalhe or {}).items() if k != "razao_social"} or None
    auditar(db, usuario.escritorio_id, "cliente_excluido", usuario, entidade="cliente", entidade_id=cliente.id)
    db.delete(cliente)
    db.commit()
