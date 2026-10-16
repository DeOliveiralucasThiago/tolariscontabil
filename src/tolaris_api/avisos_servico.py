"""Central de avisos: reúne, para toda a carteira do escritório, o que merece a atenção do contador.

Fontes: fator R e limites de receita (motor.avisos), possível imposto pago a mais em produtos monofásicos e
com ST (recuperação) e simulações salvas cujo resultado mudou com as regras atuais.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session
from tolaris_motor import PerfilEmpresa, avisos, brl, tabelas

from .acesso import _aware, agora
from .honorarios import FUSO
from .models import Cliente, DocumentoFiscal, ItemFiscal, PortalCliente, Simulacao
from .recuperacao_servico import analisar
from .servicos import diferencas, pode_recalcular, recalcular_resultado

ORDEM = {g: i for i, g in enumerate(avisos.GRAVIDADES)}
RESUMO_VAZIO = {g: 0 for g in avisos.GRAVIDADES}


_MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]


def _curta(comp: str) -> str:
    return f"{_MESES[int(comp[5:7]) - 1]}/{comp[2:4]}"


def _mes_anterior(comp: str, meses: int) -> str:
    indice = int(comp[:4]) * 12 + int(comp[5:7]) - 1 - meses
    return f"{indice // 12:04d}-{indice % 12 + 1:02d}"


def rbt12_das_notas(centavos_por_mes: dict[str, int]) -> tuple[Decimal, str]:
    """Receita dos últimos 12 meses importados e a descrição da fonte (anualiza se há menos de 12 meses)."""
    ultimo, primeiro = max(centavos_por_mes), min(centavos_por_mes)
    janela = [_mes_anterior(ultimo, n) for n in range(11, -1, -1)]
    cobertos = [c for c in janela if c >= primeiro]
    soma = Decimal(sum(centavos_por_mes.get(c, 0) for c in cobertos)) / 100
    intervalo = f"{_curta(cobertos[0])} a {_curta(ultimo)}"
    if len(cobertos) == 12:
        return soma, f"notas importadas de {intervalo}"
    return soma / len(cobertos) * 12, f"média das notas importadas de {intervalo}, x 12"


def perfil_da_simulacao(sim: Simulacao) -> PerfilEmpresa | None:
    """Perfil anual da empresa a partir de uma simulação expressa ou completa."""
    e = sim.entrada
    try:
        if sim.tipo == "completa":
            campos = {k: e[k] for k in PerfilEmpresa.__dataclass_fields__ if k in e}
            return PerfilEmpresa(**campos)
        if sim.tipo == "expressa":
            return PerfilEmpresa(
                atividade=e["atividade"],
                receita_bruta_anual=Decimal(str(e["faturamento_mensal"])) * 12,
                folha_clt_anual=Decimal(str(e["folha_mensal"])) * 12,
                pro_labore_anual=Decimal(str(e.get("pro_labore_mensal", 0))) * 12,
                ano=e.get("ano", 2026),
            )
    except (KeyError, ValueError, TypeError):
        return None
    return None


def resumo_da_mudanca(antigo: dict[str, Any], novo: dict[str, Any], mudou: list[str]) -> str:
    """Texto do que mudou: totais por regime (simulações de comparativo) e a recomendação."""
    partes = []
    for i, (a, b) in enumerate(zip(antigo.get("regimes", []), novo.get("regimes", []))):
        if f"regimes[{i}].total" in mudou:
            partes.append(f"{a['titulo']}: de {brl(a['total'])} para {brl(b['total'])} por ano")
    texto = ("Mudaram os totais — " + "; ".join(partes) + ". ") if partes else "Os valores do resultado mudaram. "
    antes, depois = antigo.get("melhor"), novo.get("melhor")
    if antes != depois:
        return texto + f"A recomendação mudou: antes {antes}, agora {depois}."
    return texto + f"A recomendação continua a mesma ({depois})."


DIAS_NAO_VISTO = 3
DIAS_SEM_RESPOSTA = 7
DIAS_MAXIMOS_DE_ACOMPANHAMENTO = 60


def _item(aviso: avisos.Aviso, cliente: Cliente, acao: dict[str, Any], chave: int | None = None) -> dict[str, Any]:
    return {
        "id": f"{aviso.codigo}-{cliente.id}" + (f"-{chave}" if chave is not None else ""),
        "codigo": aviso.codigo,
        "gravidade": aviso.gravidade,
        "titulo": aviso.titulo,
        "detalhe": aviso.detalhe,
        "valor": float(round(aviso.valor, 2)) if aviso.valor is not None else None,
        "base_legal": aviso.base_legal,
        "cliente_id": cliente.id,
        "cliente": cliente.razao_social,
        "acao": acao,
    }


def reunir(db: Session, escritorio_id: int, hoje: date | None = None) -> dict[str, Any]:
    hoje = hoje or date.today()
    clientes = list(db.scalars(select(Cliente).where(Cliente.escritorio_id == escritorio_id, Cliente.status != "inativo")))
    por_id = {c.id: c for c in clientes}

    ultimas = db.scalars(
        select(Simulacao).where(
            Simulacao.id.in_(
                select(func.max(Simulacao.id))
                .where(Simulacao.escritorio_id == escritorio_id)
                .group_by(Simulacao.cliente_id, Simulacao.tipo)
            )
        )
    )
    sims: dict[int, dict[str, Simulacao]] = defaultdict(dict)
    for s in ultimas:
        sims[s.cliente_id][s.tipo] = s

    notas: dict[int, dict[str, int]] = defaultdict(dict)
    for cid, comp, total in db.execute(
        select(DocumentoFiscal.cliente_id, DocumentoFiscal.competencia, func.sum(DocumentoFiscal.valor_centavos))
        .where(DocumentoFiscal.escritorio_id == escritorio_id, DocumentoFiscal.tipo == "saida")
        .group_by(DocumentoFiscal.cliente_id, DocumentoFiscal.competencia)
    ):
        notas[cid][comp] = total or 0
    com_itens = set(db.scalars(select(ItemFiscal.cliente_id).where(ItemFiscal.escritorio_id == escritorio_id).distinct()))

    lista: list[dict[str, Any]] = []
    for c in clientes:
        do_cliente = sims.get(c.id, {})
        base = do_cliente.get("completa") or do_cliente.get("expressa")
        perfil = perfil_da_simulacao(base) if base else None

        # Fator R (só quem está no Simples)
        if perfil is not None and c.regime_atual == "simples":
            a = avisos.avaliar_fator_r(perfil)
            if a is not None:
                lista.append(_item(a, c, {"tipo": "cliente", "rotulo": "Abrir cliente", "aba": "simulacoes"}))

        # Limites de receita
        rbt12, fonte = None, ""
        if notas.get(c.id):
            rbt12, fonte = rbt12_das_notas(notas[c.id])
        elif perfil is not None:
            rbt12, fonte = perfil.receita_bruta_anual, f"planejamento de {base.criado_em.strftime('%d/%m/%Y')}"
        if rbt12 is not None:
            for a in avisos.avaliar_limites(rbt12, c.regime_atual, hoje, fonte):
                lista.append(_item(a, c, {"tipo": "cliente", "rotulo": "Abrir cliente", "aba": "movimento" if notas.get(c.id) else "simulacoes"}))

        # Possível imposto pago a mais (monofásico e ST)
        if c.id in com_itens and c.regime_atual in (None, "simples"):
            r = analisar(db, c)
            total = Decimal(str(r["totais"]["provavel"]))
            if total > 0:
                aviso = avisos.Aviso(
                    "recuperacao", "oportunidade",
                    f"Possível imposto pago a mais: {brl(total)}",
                    f"Produtos monofásicos ou com ICMS-ST nas notas de venda ({r['periodo']['meses']} meses). "
                    f"Economia estimada de {brl(r['economia_anual'])} por ano se a receita for segregada no PGDAS-D. "
                    "Confira o que foi declarado antes de retificar.",
                    total, "LC 123/2006, art. 18, §4º-A",
                )
                lista.append(_item(aviso, c, {"tipo": "cliente", "rotulo": "Ver análise", "aba": "movimento"}))

        # Simulações salvas cujo resultado mudou com as regras atuais
        for tipo, s in do_cliente.items():
            if not pode_recalcular(tipo):
                continue
            try:
                novo = recalcular_resultado(tipo, s.entrada)
            except Exception:  # noqa: BLE001 - entrada antiga que não valida mais: não é aviso
                continue
            mudou = diferencas(s.resultado, novo)
            if not mudou:
                continue
            antes, depois = s.resultado.get("melhor"), novo.get("melhor")
            trocou = antes != depois
            ea, eb = s.resultado.get("economia_vs_pior"), novo.get("economia_vs_pior")
            detalhe = resumo_da_mudanca(s.resultado, novo, mudou)
            lista.append({
                "id": f"recalculo-{s.id}",
                "codigo": "simulacao_desatualizada",
                "gravidade": "critico" if trocou else "atencao",
                "titulo": f"{s.titulo.split(' — ')[0]}: o resultado mudou com as regras atuais"
                          + (" e a recomendação mudou" if trocou else ""),
                "detalhe": detalhe,
                "valor": float(abs((eb or 0) - (ea or 0))) or None,
                "base_legal": "",
                "cliente_id": c.id,
                "cliente": c.razao_social,
                "acao": {"tipo": "recalcular", "rotulo": "Recalcular", "simulacao_id": s.id},
            })

    lista.extend(_acompanhamentos(db, escritorio_id, por_id, agora()))

    lista.sort(key=lambda a: (ORDEM[a["gravidade"]], -(a["valor"] or 0), a["cliente"].lower()))
    resumo = dict(RESUMO_VAZIO)
    for a in lista:
        resumo[a["gravidade"]] += 1
    return {
        "avisos": lista,
        "resumo": {**resumo, "total": len(lista),
                   "valor_oportunidades": round(sum(a["valor"] or 0 for a in lista if a["gravidade"] == "oportunidade"), 2)},
        "clientes_analisados": len(por_id),
    }


def _acompanhamentos(db: Session, escritorio_id: int, clientes: dict[int, Cliente], momento) -> list[dict[str, Any]]:
    """Relatórios publicados no portal: ainda não abertos, proposta aceita e proposta vista sem resposta."""
    portais = set(db.scalars(select(PortalCliente.cliente_id).where(
        PortalCliente.escritorio_id == escritorio_id, PortalCliente.ativo.is_(True))))
    linhas = db.execute(
        select(
            Simulacao.id, Simulacao.cliente_id, Simulacao.titulo, Simulacao.publicada_em, Simulacao.criado_em,
            Simulacao.aberturas, Simulacao.visto_primeira_em, Simulacao.honorarios, Simulacao.aceite_em, Simulacao.aceite_nome,
        ).where(Simulacao.escritorio_id == escritorio_id, Simulacao.publicada.is_(True))
    )
    saida: list[dict[str, Any]] = []
    for sid, cid, titulo, publicada_em, criado_em, aberturas, visto_em, hon, aceite_em, aceite_nome in linhas:
        c = clientes.get(cid)
        if c is None:
            continue
        acao = {"tipo": "cliente", "rotulo": "Abrir cliente", "aba": "simulacoes"}
        titulo_curto = titulo.split(" — ")[0]
        mensal = hon["valor_mensal"] if hon else None
        if aceite_em is not None and c.status == "prospect":
            quando = _aware(aceite_em).astimezone(FUSO).strftime("%d/%m/%Y às %H:%M")
            saida.append(_item(avisos.Aviso(
                "proposta_aceita", "oportunidade", f"{aceite_nome} aceitou a proposta de honorários: {brl(mensal)} por mês",
                f"Aceite eletrônico registrado em {quando}. Cadastre o cliente como ativo e formalize o contrato de "
                "prestação de serviços.", Decimal(str(mensal)) * 12), c, {**acao, "aba": "dados"}, sid))
        elif hon and aceite_em is None and visto_em is not None:
            dias = (momento - _aware(visto_em)).days
            if dias >= DIAS_SEM_RESPOSTA:
                saida.append(_item(avisos.Aviso(
                    "proposta_sem_resposta", "atencao", f"Proposta de honorários vista há {dias} dias e sem resposta",
                    f"O cliente abriu \"{titulo_curto}\" e não aceitou a proposta de {brl(mensal)} por mês. "
                    "Vale um contato por telefone ou WhatsApp.", Decimal(str(mensal)) * 12), c, acao, sid))
        if aberturas == 0 and cid in portais:
            dias = (momento - _aware(publicada_em or criado_em)).days
            if DIAS_NAO_VISTO <= dias <= DIAS_MAXIMOS_DE_ACOMPANHAMENTO:
                saida.append(_item(avisos.Aviso(
                    "relatorio_nao_visto", "info", f"O cliente ainda não abriu \"{titulo_curto}\"",
                    f"Publicado no portal há {dias} dias. Vale lembrar o cliente por WhatsApp ou e-mail."), c, acao, sid))
    return saida


def mudancas(hoje: date | None = None) -> list[dict[str, Any]]:
    """Mudanças na legislação já incorporadas ao motor, das mais próximas das de hoje para as mais distantes."""
    hoje = hoje or date.today()
    itens = []
    for m in tabelas.carregar("mudancas")["mudancas"]:
        inicio = date.fromisoformat(m["data"])
        itens.append({**m, "vigente": inicio <= hoje, "dias": (inicio - hoje).days})
    vigentes = sorted((i for i in itens if i["vigente"]), key=lambda i: i["data"], reverse=True)
    futuras = sorted((i for i in itens if not i["vigente"]), key=lambda i: i["data"])
    return futuras + vigentes
