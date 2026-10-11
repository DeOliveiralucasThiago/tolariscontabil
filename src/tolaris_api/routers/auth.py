from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Escritorio, Usuario
from ..schemas import CadastroEntrada, EscritorioSaida, LoginEntrada, SessaoSaida, UsuarioSaida
from ..seguranca import apagar_cookie, criar_token, definir_cookie, hash_senha, usuario_atual, verificar_senha

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


@router.post("/cadastro", response_model=SessaoSaida, status_code=status.HTTP_201_CREATED)
def cadastrar(dados: CadastroEntrada, resposta: Response, db: Session = Depends(get_db)) -> SessaoSaida:
    email = dados.email.lower()
    if db.scalar(select(func.count()).select_from(Usuario).where(Usuario.email == email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "E-mail já cadastrado")
    esc = Escritorio(nome=dados.escritorio_nome.strip(), contador_responsavel=dados.nome.strip(), email=email)
    usuario = Usuario(escritorio=esc, nome=dados.nome.strip(), email=email, senha_hash=hash_senha(dados.senha))
    db.add_all([esc, usuario])
    db.commit()
    definir_cookie(resposta, criar_token(usuario))
    return sessao(usuario)


@router.post("/login", response_model=SessaoSaida)
def login(dados: LoginEntrada, resposta: Response, db: Session = Depends(get_db)) -> SessaoSaida:
    usuario = db.scalar(select(Usuario).where(Usuario.email == dados.email.lower()))
    valido = verificar_senha(dados.senha, usuario.senha_hash if usuario else _HASH_FALSO)
    if not usuario or not valido or not usuario.ativo:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "E-mail ou senha incorretos")
    definir_cookie(resposta, criar_token(usuario))
    return sessao(usuario)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(resposta: Response) -> None:
    apagar_cookie(resposta)


@router.get("/me", response_model=SessaoSaida)
def me(usuario: Usuario = Depends(usuario_atual)) -> SessaoSaida:
    return sessao(usuario)
