"""Importação de clientes em lote: uma planilha com CNPJ (e, se houver, razão social, e-mail, telefone...).

O que faltar é completado depois pela consulta de CNPJ, em lotes pequenos, para respeitar o limite da API pública.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from typing import Any

from pydantic import EmailStr, TypeAdapter, ValidationError

from . import planilha as pl
from .cnpj import cnpj_valido, formatar_cnpj, so_digitos

CAMPOS = ("cnpj", "razao_social", "nome_fantasia", "atividade", "regime_atual", "status", "contato_nome", "email", "telefone", "observacoes")
ROTULOS = {
    "cnpj": "CNPJ",
    "razao_social": "Razão social",
    "nome_fantasia": "Nome fantasia",
    "atividade": "Atividade (comércio, indústria, serviços)",
    "regime_atual": "Regime atual",
    "status": "Situação do cliente",
    "contato_nome": "Nome do contato",
    "email": "E-mail",
    "telefone": "Telefone",
    "observacoes": "Observações",
}
SINONIMOS = {
    "cnpj": ["cnpj", "cnpj cpf", "documento"],
    "razao_social": ["razao social", "nome da empresa", "empresa", "cliente", "nome"],
    "nome_fantasia": ["nome fantasia", "fantasia"],
    "atividade": ["atividade", "ramo", "tipo de atividade"],
    "regime_atual": ["regime tributario", "regime atual", "regime", "enquadramento"],
    "status": ["situacao do cliente", "status", "situacao"],
    "contato_nome": ["contato", "responsavel", "nome do contato"],
    "email": ["e mail", "email"],
    "telefone": ["telefone", "celular", "whatsapp", "fone"],
    "observacoes": ["observacoes", "observacao", "obs"],
}
LIMITE_CLIENTES = 2000

_ATIVIDADES = {
    "comercio": "comercio", "industria": "industria", "servico fator r": "servico_fator_r", "servicos fator r": "servico_fator_r",
    "servico anexo iii": "servico_anexo_iii", "servicos anexo iii": "servico_anexo_iii",
    "servico anexo iv": "servico_anexo_iv", "servicos anexo iv": "servico_anexo_iv",
}
_REGIMES = {
    "mei": "mei", "simples": "simples", "simples nacional": "simples", "presumido": "presumido", "lucro presumido": "presumido",
    "real": "real", "lucro real": "real", "outro": "outro", "outros": "outro",
}
_STATUS = {"ativo": "ativo", "ativa": "ativo", "inativo": "inativo", "inativa": "inativo", "prospect": "prospect"}
_EMAIL = TypeAdapter(EmailStr)


@dataclass
class LinhaLida:
    numero: int
    cnpj: str
    dados: dict[str, Any] = field(default_factory=dict)


@dataclass
class Leitura:
    linhas: list[LinhaLida] = field(default_factory=list)
    invalidas: list[tuple[int, str | None, str]] = field(default_factory=list)
    """(linha, cnpj ou texto original, motivo)."""
    avisos: list[str] = field(default_factory=list)


def modelo_csv() -> bytes:
    linhas = [
        ["CNPJ", "Razão social", "Atividade", "Regime", "E-mail", "Telefone", "Contato"],
        ["11.222.333/0001-81", "Padaria Pão Bom Ltda", "Comércio", "Simples Nacional", "contato@padaria.com.br", "(11) 98765-4321", "Marcos Souza"],
        ["45.997.418/0001-53", "", "", "", "", "", ""],
    ]
    saida = io.StringIO()
    csv.writer(saida, delimiter=";", lineterminator="\r\n").writerows(linhas)
    return ("﻿" + saida.getvalue()).encode("utf-8")


def normalizar_cnpj(texto: str) -> str | None:
    """CNPJ com ou sem pontuação; o Excel come zeros à esquerda, então completa com zeros antes de validar."""
    d = so_digitos(texto)
    if not 8 <= len(d) <= 14:
        return None
    d = d.zfill(14)
    return d if cnpj_valido(d) else None


def _valor(linha: list[str], mapa: dict[str, int], campo: str) -> str:
    i = mapa.get(campo)
    return linha[i].strip() if i is not None and i < len(linha) else ""


def ler(linhas: list[list[str]], mapa: dict[str, int]) -> Leitura:
    leitura = Leitura()
    if len(linhas) > LIMITE_CLIENTES:
        raise pl.PlanilhaInvalida(f"Mais de {LIMITE_CLIENTES} clientes de uma vez; divida a planilha")
    ignorados: dict[str, set[str]] = {}
    for n, linha in enumerate(linhas, start=2):
        bruto = _valor(linha, mapa, "cnpj")
        if not bruto:
            continue  # linha em branco no meio da planilha
        cnpj = normalizar_cnpj(bruto)
        if cnpj is None:
            leitura.invalidas.append((n, bruto[:30], "CNPJ inválido"))
            continue
        dados: dict[str, Any] = {}
        for campo in ("razao_social", "nome_fantasia", "contato_nome", "observacoes"):
            v = _valor(linha, mapa, campo)
            if v:
                dados[campo] = v[:250] if campo != "observacoes" else v[:5000]
        for campo, tabela in (("atividade", _ATIVIDADES), ("regime_atual", _REGIMES), ("status", _STATUS)):
            v = _valor(linha, mapa, campo)
            if not v:
                continue
            achado = tabela.get(pl._normalizar(v))
            if achado:
                dados[campo] = achado
            else:
                ignorados.setdefault(campo, set()).add(v[:30])
        email = _valor(linha, mapa, "email")
        if email:
            try:
                dados["email"] = str(_EMAIL.validate_python(email)).lower()
            except ValidationError:
                ignorados.setdefault("email", set()).add(email[:40])
        telefone = _valor(linha, mapa, "telefone")
        if telefone:
            dados["telefone"] = telefone[:40]
        if "razao_social" in dados and len(dados["razao_social"]) < 2:
            del dados["razao_social"]
        leitura.linhas.append(LinhaLida(n, cnpj, dados))
    nomes = {"atividade": "atividade", "regime_atual": "regime", "status": "situação", "email": "e-mail"}
    for campo, valores in ignorados.items():
        exemplos = ", ".join(f"“{v}”" for v in sorted(valores)[:3])
        leitura.avisos.append(f"Valores de {nomes[campo]} não reconhecidos foram deixados em branco: {exemplos}.")
    return leitura


def placeholder(cnpj: str) -> str:
    return f"CNPJ {formatar_cnpj(cnpj)}"
