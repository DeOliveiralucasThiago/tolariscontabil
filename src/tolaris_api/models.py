"""Modelos do banco. Toda entidade de negócio pertence a um escritório (multi-tenant)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import JSON, ForeignKey, LargeBinary, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def agora() -> datetime:
    return datetime.now(timezone.utc)


class Escritorio(Base):
    __tablename__ = "escritorios"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(200))
    cnpj: Mapped[str | None] = mapped_column(String(14))
    contador_responsavel: Mapped[str | None] = mapped_column(String(200))
    crc: Mapped[str | None] = mapped_column(String(40))
    email: Mapped[str | None] = mapped_column(String(200))
    telefone: Mapped[str | None] = mapped_column(String(40))
    cor_primaria: Mapped[str] = mapped_column(String(7), default="#1F3A5F")
    logo: Mapped[bytes | None] = mapped_column(LargeBinary, deferred=True)
    logo_mime: Mapped[str | None] = mapped_column(String(40))
    criado_em: Mapped[datetime] = mapped_column(default=agora)

    usuarios: Mapped[list[Usuario]] = relationship(back_populates="escritorio")


class Usuario(Base):
    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(primary_key=True)
    escritorio_id: Mapped[int] = mapped_column(ForeignKey("escritorios.id", ondelete="CASCADE"), index=True)
    nome: Mapped[str] = mapped_column(String(200))
    email: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    senha_hash: Mapped[str] = mapped_column(String(300))
    papel: Mapped[str] = mapped_column(String(20), default="admin")
    ativo: Mapped[bool] = mapped_column(default=True)
    criado_em: Mapped[datetime] = mapped_column(default=agora)

    escritorio: Mapped[Escritorio] = relationship(back_populates="usuarios")


class Cliente(Base):
    __tablename__ = "clientes"
    __table_args__ = (UniqueConstraint("escritorio_id", "cnpj", name="uq_cliente_cnpj_por_escritorio"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    escritorio_id: Mapped[int] = mapped_column(ForeignKey("escritorios.id", ondelete="CASCADE"), index=True)
    razao_social: Mapped[str] = mapped_column(String(250))
    nome_fantasia: Mapped[str | None] = mapped_column(String(250))
    cnpj: Mapped[str | None] = mapped_column(String(14))
    cnae_principal: Mapped[str | None] = mapped_column(String(7))
    cnae_descricao: Mapped[str | None] = mapped_column(String(300))
    municipio: Mapped[str | None] = mapped_column(String(120))
    uf: Mapped[str | None] = mapped_column(String(2))
    atividade: Mapped[str | None] = mapped_column(String(30))
    regime_atual: Mapped[str | None] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(20), default="prospect", index=True)
    contato_nome: Mapped[str | None] = mapped_column(String(200))
    email: Mapped[str | None] = mapped_column(String(200))
    telefone: Mapped[str | None] = mapped_column(String(40))
    observacoes: Mapped[str | None] = mapped_column(Text)
    criado_em: Mapped[datetime] = mapped_column(default=agora)
    atualizado_em: Mapped[datetime] = mapped_column(default=agora, onupdate=agora)

    simulacoes: Mapped[list[Simulacao]] = relationship(
        back_populates="cliente", cascade="all, delete-orphan", order_by="Simulacao.criado_em.desc()"
    )


class Simulacao(Base):
    __tablename__ = "simulacoes"

    id: Mapped[int] = mapped_column(primary_key=True)
    escritorio_id: Mapped[int] = mapped_column(ForeignKey("escritorios.id", ondelete="CASCADE"), index=True)
    cliente_id: Mapped[int] = mapped_column(ForeignKey("clientes.id", ondelete="CASCADE"), index=True)
    criado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    tipo: Mapped[str] = mapped_column(String(20))
    titulo: Mapped[str] = mapped_column(String(200))
    entrada: Mapped[dict[str, Any]] = mapped_column(JSON)
    resultado: Mapped[dict[str, Any]] = mapped_column(JSON)
    versao_motor: Mapped[str] = mapped_column(String(20))
    criado_em: Mapped[datetime] = mapped_column(default=agora, index=True)

    cliente: Mapped[Cliente] = relationship(back_populates="simulacoes")
