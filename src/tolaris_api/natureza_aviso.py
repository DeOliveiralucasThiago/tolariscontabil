"""Aviso da Central quando a natureza jurídica do cadastro não combina com o regime em que o cliente está."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from tolaris_motor import avisos, natureza_juridica

from .impedimentos_servico import achados_do_cliente
from .models import Cliente

ACAO = {"tipo": "cliente", "rotulo": "Abrir dados cadastrais", "aba": "dados"}


def aviso_natureza(cliente: Cliente) -> tuple[avisos.Aviso, dict[str, Any]] | None:
    """Crítico quando o cliente está no Simples (ou é MEI) e a natureza jurídica não permite; ``None`` se está tudo certo ou sem dados."""
    n = natureza_juridica.classificar(cliente.natureza_juridica, cliente.natureza_juridica_codigo)
    if n is None:
        return None
    if cliente.regime_atual == "mei" and not n.mei:
        return (
            avisos.Aviso(
                "natureza_mei", "critico", f"MEI só vale para empresário individual: o cadastro diz \"{n.rotulo}\"",
                f"{n.explicacao} Quem muda para outra natureza jurídica é desenquadrado do MEI (LC 123/2006, art. 18-A, § 16, I). Confira o cadastro "
                "na Receita e o regime do cliente.",
                None, natureza_juridica.BASE_LEGAL_MEI,
            ),
            ACAO,
        )
    if cliente.regime_atual == "simples" and natureza_juridica.impede_simples(n):
        return (
            avisos.Aviso(
                "natureza_simples", "critico", f"A natureza jurídica \"{n.rotulo}\" não permite o Simples Nacional",
                f"{n.explicacao} Se o cliente recolhe o DAS, confirme o cadastro e a opção na Receita; pode haver exclusão do Simples e cobrança dos tributos "
                "pelo regime normal.",
                None, natureza_juridica.BASE_LEGAL_ELEGIBILIDADE,
            ),
            ACAO,
        )
    return None


def aviso_impedimentos(cliente: Cliente, receita: Decimal | None) -> tuple[avisos.Aviso, dict[str, Any]] | None:
    """Crítico quando o cliente está no Simples e a conferência confirmou um impedimento; atenção quando ele depende da receita das outras empresas."""
    if cliente.regime_atual != "simples":
        return None
    achados = achados_do_cliente(cliente, receita)
    impedem = [a for a in achados if a.status == "impede"]
    dependem = [a for a in achados if a.status == "depende_da_receita"]
    if impedem:
        lista = "; ".join(f"{a.texto} ({a.base_legal})" for a in impedem)
        return (
            avisos.Aviso(
                "impedimento_simples", "critico", f"Impedimento ao Simples Nacional confirmado no cadastro ({len(impedem)})",
                f"{lista}. Quem incorre em impedimento é excluído do Simples com efeitos a partir do mês seguinte (LC 123/2006, art. 3º, § 6º): "
                "confirme a situação e, se for o caso, a comunicação de exclusão e a mudança de regime.",
                None, "LC 123/2006, art. 3º, §§ 4º e 6º, e art. 17",
            ),
            ACAO,
        )
    if dependem:
        return (
            avisos.Aviso(
                "impedimento_simples_receita", "atencao", "Impedimento ao Simples que depende da receita das outras empresas dos sócios",
                "; ".join(f"{a.texto} ({a.base_legal})" for a in dependem)
                + f". O impedimento só vale se a receita bruta global passar de R$ 4.800.000: informe a receita das outras empresas dos sócios na conferência.",
                None, "LC 123/2006, art. 3º, § 4º, III a V",
            ),
            ACAO,
        )
    return None
