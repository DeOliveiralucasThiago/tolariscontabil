"use client";

import { useEffect, useState } from "react";

import { api } from "@/lib/api";
import type { BuscaDeCnae, CnaeDoCatalogo, ConfiancaCnae, OpcoesDeCnae } from "@/lib/tipos";

import { Cartao, Selecao, classeCampo, Rotulo } from "./ui";

const ROTULO_CONFIANCA: Record<ConfiancaCnae, { texto: string; ajuda: string }> = {
  oficial: { texto: "Resolução CGSN", ajuda: "Vem dos Anexos VI e VII da Resolução CGSN 140/2018" },
  tabela: { texto: "Tabela comercial", ajuda: "Anexo conforme a tabela da Contabilizei: confira na descrição da atividade" },
  divisao: { texto: "Aproximado", ajuda: "Regra aproximada pela divisão do CNAE: este código não está na tabela de Anexos" },
};

export function SeloConfianca({ confianca }: { confianca: ConfiancaCnae }) {
  const c = ROTULO_CONFIANCA[confianca];
  const cor = confianca === "oficial" ? "bg-emerald-50 text-emerald-800" : confianca === "tabela" ? "bg-sky-50 text-sky-800" : "bg-amber-50 text-amber-900";
  return (
    <span title={c.ajuda} className={`rounded px-1.5 py-0.5 text-[11px] ${cor}`}>
      {c.texto}
    </span>
  );
}

function Linha({ c }: { c: CnaeDoCatalogo }) {
  const vedado = c.vedacao === "impeditivo";
  return (
    <li className="flex flex-col gap-1 py-2.5 text-sm sm:flex-row sm:items-start sm:justify-between" data-testid="linha-cnae">
      <div className="min-w-0">
        <span className="num font-medium">{c.codigo_formatado}</span> {c.descricao}
        <div className="text-xs text-tinta-2">{c.divisao} · {c.divisao_nome}</div>
      </div>
      <div className="flex shrink-0 flex-wrap items-center gap-1.5 sm:justify-end">
        <span className={vedado ? "font-medium text-red-700" : "font-medium"}>{c.anexo}</span>
        {c.vedacao === "ambiguo" && <span className="rounded bg-amber-50 px-1.5 py-0.5 text-[11px] text-amber-900">Ambíguo no Simples</span>}
        <SeloConfianca confianca={c.confianca} />
      </div>
    </li>
  );
}

/** Procura em todos os CNAEs (IBGE) com o Anexo provável de cada um e as vedações do Simples. */
export function BuscaCnae({ filtroInicial = "" }: { filtroInicial?: string }) {
  const [texto, setTexto] = useState("");
  const [filtro, setFiltro] = useState(filtroInicial);
  const [divisao, setDivisao] = useState("");
  const [opcoes, setOpcoes] = useState<OpcoesDeCnae | null>(null);
  const [res, setRes] = useState<BuscaDeCnae | null>(null);
  const [erro, setErro] = useState("");

  useEffect(() => {
    api<OpcoesDeCnae>("/cnae/divisoes").then(setOpcoes).catch(() => setOpcoes(null));
  }, []);

  useEffect(() => {
    const espera = setTimeout(() => {
      const q = new URLSearchParams({ q: texto.trim(), limite: "40" });
      if (filtro) q.set("anexo", filtro);
      if (divisao) q.set("divisao", divisao);
      if (filtro === "iii_direto") q.set("so_da_tabela", "true");
      api<BuscaDeCnae>(`/cnae?${q}`)
        .then((r) => {
          setRes(r);
          setErro("");
        })
        .catch(() => setErro("Não foi possível consultar os CNAEs agora."));
    }, 250);
    return () => clearTimeout(espera);
  }, [texto, filtro, divisao]);

  return (
    <div data-testid="busca-cnae">
      <Cartao titulo="Explorar CNAEs">
        <p className="mb-3 text-sm text-tinta-2">
          Todos os CNAEs do IBGE, com o Anexo provável e as vedações do Simples. Para uma empresa no Anexo V, o filtro “Anexo III direto”
          mostra atividades que tributam no Anexo III sem depender do fator R. <strong>Só vale se a empresa exerce a atividade de fato.</strong>
        </p>
        <div className="grid gap-3 sm:grid-cols-3">
          <div>
            <Rotulo htmlFor="busca_cnae_texto">Código ou descrição</Rotulo>
            <input id="busca_cnae_texto" className={classeCampo} value={texto} onChange={(e) => setTexto(e.target.value)} placeholder="Ex.: treinamento, 8599" />
          </div>
          <Selecao rotulo="Anexo" name="busca_cnae_anexo" value={filtro} onChange={(e) => setFiltro(e.target.value)}>
            <option value="">Todos</option>
            {opcoes?.filtros.map((f) => (
              <option key={f.codigo} value={f.codigo}>{f.nome}</option>
            ))}
          </Selecao>
          <Selecao rotulo="Área (divisão do CNAE)" name="busca_cnae_divisao" value={divisao} onChange={(e) => setDivisao(e.target.value)}>
            <option value="">Todas</option>
            {opcoes?.divisoes.map((d) => (
              <option key={d.codigo} value={d.codigo}>{d.codigo} — {d.nome.charAt(0) + d.nome.slice(1).toLowerCase()}</option>
            ))}
          </Selecao>
        </div>
        {erro && <p role="alert" className="mt-3 text-sm text-red-700">{erro}</p>}
        {res && (
          <>
            <p className="mt-4 text-xs text-tinta-2" data-testid="total-cnae">
              {res.total} CNAE{res.total === 1 ? "" : "s"} encontrado{res.total === 1 ? "" : "s"}
              {res.total > res.itens.length ? ` (mostrando ${res.itens.length}; refine a busca)` : ""}
            </p>
            <ul className="mt-1 divide-y divide-borda">
              {res.itens.map((c) => (
                <Linha key={c.codigo} c={c} />
              ))}
            </ul>
            <p className="mt-3 text-xs text-tinta-2">
              Fontes: {res.fontes.subclasses}. Vedações: {res.fontes.vedacao}. Anexos: {res.fontes.anexos}. Coletado em {res.fontes.atualizado_em}.
              A Resolução CGSN 140/2018 define o Anexo pela descrição da atividade (art. 25, § 1º); não existe tabela oficial por CNAE.
            </p>
          </>
        )}
      </Cartao>
    </div>
  );
}
