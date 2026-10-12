from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response, status
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from ..acesso import (
    agora,
    criar_token,
    ip_cliente,
    limite_envio_redefinicao,
    registrar_tentativa,
    token_valido,
    verificar_limite_login,
)
from ..config import get_settings
from ..db import get_db
from ..emails import Mensagem, enviar_sem_falhar, montar_html
from ..models import Escritorio, TokenAcesso, Usuario
from ..schemas import (
    AlterarSenhaEntrada,
    CadastroEntrada,
    EscritorioSaida,
    EsqueciSenhaEntrada,
    LoginEntrada,
    RedefinirSenhaEntrada,
    SessaoSaida,
    UsuarioSaida,
)
from ..seguranca import apagar_cookie, criar_token as criar_jwt, definir_cookie, hash_senha, usuario_atual, verificar_senha

router = APIRouter(prefix="/auth", tags=["autenticação"])

# Hash fixo para gastar o mesmo tempo quando o e-mail não existe (evita enumeração por tempo).
_HASH_FALSO = hash_senha("senha-inexistente")


def sessao(usuario: Usuario) -> SessaoSaida:
    esc = usuario.escritorio
    return SessaoSaida(
        usuario=UsuarioSaida.model_validate(usuario),
        escritorio=EscritorioSaida(
            id=esc.id,
            nome=esc.nome,
            cnpj=esc.cnpj,
            contador_responsavel=esc.contador_responsavel,
            crc=esc.crc,
            email=esc.email,
            telefone=esc.telefone,
            cor_primaria=esc.cor_primaria,
            tem_logo=esc.logo_mime is not None,
        ),
    )


def email_em_uso(db: Session, email: str) -> bool:
    return bool(db.scalar(select(func.count()).select_from(Usuario).where(Usuario.email == email)))


@router.post("/cadastro", response_model=SessaoSaida, status_code=status.HTTP_201_CREATED)
def cadastrar(dados: CadastroEntrada, resposta: Response, db: Session = Depends(get_db)) -> SessaoSaida:
    email = dados.email.lower()
    if email_em_uso(db, email):
        raise HTTPException(status.HTTP_409_CONFLICT, "E-mail já cadastrado")
    esc = Escritorio(nome=dados.escritorio_nome.strip(), contador_responsavel=dados.nome.strip(), email=email)
    usuario = Usuario(escritorio=esc, nome=dados.nome.strip(), email=email, senha_hash=hash_senha(dados.senha))
    db.add_all([esc, usuario])
    db.commit()
    definir_cookie(resposta, criar_jwt(usuario))
    return sessao(usuario)


@router.post("/login", response_model=SessaoSaida)
def login(dados: LoginEntrada, request: Request, resposta: Response, db: Session = Depends(get_db)) -> SessaoSaida:
    email, ip = dados.email.lower(), ip_cliente(request)
    verificar_limite_login(db, email, ip)
    usuario = db.scalar(select(Usuario).where(Usuario.email == email))
    valido = verificar_senha(dados.senha, usuario.senha_hash if usuario else _HASH_FALSO)
    if not usuario or not valido or not usuario.ativo:
        registrar_tentativa(db, email, ip, False)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "E-mail ou senha incorretos")
    registrar_tentativa(db, email, ip, True)
    definir_cookie(resposta, criar_jwt(usuario))
    return sessao(usuario)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(resposta: Response) -> None:
    apagar_cookie(resposta)


@router.get("/me", response_model=SessaoSaida)
def me(usuario: Usuario = Depends(usuario_atual)) -> SessaoSaida:
    return sessao(usuario)


# --- Senha ---------------------------------------------------------------------------
@router.post("/esqueci-senha", status_code=status.HTTP_202_ACCEPTED)
def esqueci_senha(dados: EsqueciSenhaEntrada, tarefas: BackgroundTasks, db: Session = Depends(get_db)) -> dict:
    """Sempre responde igual, exista ou não o e-mail (não revela quem tem conta)."""
    cfg = get_settings()
    email = dados.email.lower()
    usuario = db.scalar(select(Usuario).where(Usuario.email == email))
    if usuario and usuario.ativo and limite_envio_redefinicao(db, email):
        token, _ = criar_token(
            db, "redefinir_senha", usuario.escritorio_id, email,
            timedelta(minutes=cfg.token_redefinicao_minutos), usuario_id=usuario.id,
        )
        db.commit()
        link = f"{cfg.url_publica}/redefinir-senha?token={token}"
        tarefas.add_task(
            enviar_sem_falhar,
            Mensagem(
                para=[email],
                assunto="Redefinição de senha — Tolaris Contábil",
                texto=f"Olá, {usuario.nome}.\n\nPara criar uma nova senha, acesse:\n{link}\n\n"
                      f"O link vale por {cfg.token_redefinicao_minutos} minutos. Se não foi você, ignore este e-mail.",
                html=montar_html(
                    "Redefinição de senha",
                    [f"Olá, {usuario.nome}.", "Recebemos um pedido para redefinir a sua senha.",
                     f"O link vale por {cfg.token_redefinicao_minutos} minutos. Se não foi você, ignore este e-mail."],
                    botao=("Criar nova senha", link),
                ),
            ),
        )
    return {"mensagem": "Se o e-mail estiver cadastrado, enviaremos um link para redefinir a senha."}


@router.post("/redefinir-senha", response_model=SessaoSaida)
def redefinir_senha(dados: RedefinirSenhaEntrada, resposta: Response, db: Session = Depends(get_db)) -> SessaoSaida:
    registro = token_valido(db, "redefinir_senha", dados.token)
    usuario = db.get(Usuario, registro.usuario_id)
    if usuario is None or not usuario.ativo:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Link inválido ou expirado. Peça um novo.")
    usuario.senha_hash = hash_senha(dados.senha)
    usuario.sessao_versao += 1  # derruba sessões abertas com a senha antiga
    # Invalida este e qualquer outro link de redefinição pendente do usuário
    db.execute(
        update(TokenAcesso)
        .where(TokenAcesso.usuario_id == usuario.id, TokenAcesso.tipo == "redefinir_senha", TokenAcesso.usado_em.is_(None))
        .values(usado_em=agora())
    )
    db.commit()
    definir_cookie(resposta, criar_jwt(usuario))
    return sessao(usuario)


@router.post("/alterar-senha", response_model=SessaoSaida)
def alterar_senha(
    dados: AlterarSenhaEntrada, resposta: Response, usuario: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)
) -> SessaoSaida:
    if not verificar_senha(dados.senha_atual, usuario.senha_hash):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Senha atual incorreta")
    usuario.senha_hash = hash_senha(dados.nova_senha)
    usuario.sessao_versao += 1
    db.commit()
    definir_cookie(resposta, criar_jwt(usuario))  # mantém esta sessão, derruba as outras
    return sessao(usuario)
