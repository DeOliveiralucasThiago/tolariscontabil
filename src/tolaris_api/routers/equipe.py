from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..acesso import agora, criar_token, token_valido
from ..config import get_settings
from ..db import get_db
from ..emails import Mensagem, enviar_sem_falhar, montar_html
from ..models import Escritorio, TokenAcesso, Usuario
from ..schemas import (
    AceitarConviteEntrada,
    ConviteEntrada,
    ConvitePublico,
    ConviteSaida,
    EquipeSaida,
    MembroAtualizar,
    MembroSaida,
    SessaoSaida,
)
from ..seguranca import criar_token as criar_jwt, definir_cookie, hash_senha, somente_admin, usuario_atual
from .auth import email_em_uso, sessao

router = APIRouter(tags=["equipe"])


def _convites_pendentes(db: Session, escritorio_id: int) -> list[TokenAcesso]:
    return list(
        db.scalars(
            select(TokenAcesso)
            .where(
                TokenAcesso.escritorio_id == escritorio_id,
                TokenAcesso.tipo == "convite",
                TokenAcesso.usado_em.is_(None),
                TokenAcesso.expira_em > agora(),
            )
            .order_by(TokenAcesso.criado_em.desc())
        )
    )


@router.get("/equipe", response_model=EquipeSaida)
def listar(usuario: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)) -> EquipeSaida:
    membros = db.scalars(select(Usuario).where(Usuario.escritorio_id == usuario.escritorio_id).order_by(Usuario.nome))
    convites = _convites_pendentes(db, usuario.escritorio_id) if usuario.papel == "admin" else []
    return EquipeSaida(
        membros=[MembroSaida.model_validate(m) for m in membros],
        convites=[ConviteSaida.model_validate(c) for c in convites],
    )


@router.post("/equipe/convites", response_model=ConviteSaida, status_code=status.HTTP_201_CREATED)
def convidar(
    dados: ConviteEntrada, tarefas: BackgroundTasks, admin: Usuario = Depends(somente_admin), db: Session = Depends(get_db)
) -> TokenAcesso:
    cfg = get_settings()
    email = dados.email.lower()
    if email_em_uso(db, email):
        raise HTTPException(status.HTTP_409_CONFLICT, "Este e-mail já tem uma conta no Tolaris")
    # Um convite pendente por e-mail: o novo substitui o anterior
    for antigo in _convites_pendentes(db, admin.escritorio_id):
        if antigo.email == email:
            antigo.usado_em = agora()
    token, convite = criar_token(
        db, "convite", admin.escritorio_id, email, timedelta(days=cfg.convite_dias),
        nome=dados.nome, papel=dados.papel, criado_por_id=admin.id,
    )
    db.commit()
    escritorio = admin.escritorio
    link = f"{cfg.url_publica}/convite?token={token}"
    tarefas.add_task(
        enviar_sem_falhar,
        Mensagem(
            para=[email],
            assunto=f"Convite para a equipe {escritorio.nome} no Tolaris",
            texto=f"{admin.nome} convidou você para a equipe {escritorio.nome} no Tolaris Contábil.\n\n"
                  f"Aceite em: {link}\n\nO convite vale por {cfg.convite_dias} dias.",
            html=montar_html(
                f"Convite para {escritorio.nome}",
                [f"{admin.nome} convidou você para a equipe {escritorio.nome} no Tolaris Contábil.",
                 f"O convite vale por {cfg.convite_dias} dias."],
                cor=escritorio.cor_primaria,
                botao=("Aceitar convite", link),
            ),
            nome_remetente=escritorio.nome,
            responder_para=admin.email,
        ),
    )
    return convite


@router.delete("/equipe/convites/{convite_id}", status_code=status.HTTP_204_NO_CONTENT)
def revogar(convite_id: int, admin: Usuario = Depends(somente_admin), db: Session = Depends(get_db)) -> None:
    convite = db.get(TokenAcesso, convite_id)
    if convite is None or convite.tipo != "convite" or convite.escritorio_id != admin.escritorio_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Convite não encontrado")
    convite.usado_em = agora()
    db.commit()


def _admins_ativos(db: Session, escritorio_id: int) -> int:
    return db.scalar(
        select(func.count()).select_from(Usuario).where(
            Usuario.escritorio_id == escritorio_id, Usuario.papel == "admin", Usuario.ativo.is_(True)
        )
    ) or 0


@router.patch("/equipe/{usuario_id}", response_model=MembroSaida)
def atualizar_membro(
    usuario_id: int, dados: MembroAtualizar, admin: Usuario = Depends(somente_admin), db: Session = Depends(get_db)
) -> Usuario:
    membro = db.get(Usuario, usuario_id)
    if membro is None or membro.escritorio_id != admin.escritorio_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Usuário não encontrado")
    perde_admin = membro.papel == "admin" and membro.ativo and (dados.papel == "membro" or dados.ativo is False)
    if perde_admin and _admins_ativos(db, admin.escritorio_id) <= 1:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "O escritório precisa de pelo menos um administrador ativo")
    if dados.papel is not None:
        membro.papel = dados.papel
    if dados.ativo is not None and dados.ativo != membro.ativo:
        membro.ativo = dados.ativo
        membro.sessao_versao += 1  # desativado: cai na hora
    db.commit()
    return membro


# --- Aceite (público, pelo link do e-mail) ---------------------------------------------------
@router.get("/convites/{token}", response_model=ConvitePublico)
def ver_convite(token: str, db: Session = Depends(get_db)) -> ConvitePublico:
    convite = token_valido(db, "convite", token)
    escritorio = db.get(Escritorio, convite.escritorio_id)
    return ConvitePublico(escritorio=escritorio.nome, email=convite.email, nome=convite.nome, papel=convite.papel)


@router.post("/convites/aceitar", response_model=SessaoSaida, status_code=status.HTTP_201_CREATED)
def aceitar(dados: AceitarConviteEntrada, resposta: Response, db: Session = Depends(get_db)) -> SessaoSaida:
    convite = token_valido(db, "convite", dados.token)
    if email_em_uso(db, convite.email):
        raise HTTPException(status.HTTP_409_CONFLICT, "Este e-mail já tem uma conta. Entre com ela.")
    usuario = Usuario(
        escritorio_id=convite.escritorio_id,
        nome=dados.nome.strip(),
        email=convite.email,
        senha_hash=hash_senha(dados.senha),
        papel=convite.papel or "membro",
    )
    convite.usado_em = agora()
    db.add(usuario)
    db.commit()
    definir_cookie(resposta, criar_jwt(usuario))
    return sessao(usuario)
