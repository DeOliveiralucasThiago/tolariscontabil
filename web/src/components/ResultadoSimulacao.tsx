"use client";

import type { ReactNode } from "react";

import { brl, dataHora } from "@/lib/formato";
import type {
  ResultadoAutonomo as TAutonomo,
  ResultadoProLabore as TProLabore,
  ResultadoRecuperacao as TRecuperacao,
  InfoRecalculo,
  ResultadoReforma as TReforma,
  ResultadoSimplesReforma as TSimplesReforma,
  Simulacao,
} from "@/lib/tipos";

import { ResultadoComparativo } from "./ResultadoComparativo";
import { ResultadoRecuperacao } from "./ResultadoRecuperacao";
import { ResultadoAutonomo, ResultadoProLabore, ResultadoReforma, ResultadoSimplesReforma } from "./ResultadosFase2";

/** Aviso no topo de uma simulação que foi refeita com as regras atuais. */
function FaixaRecalculo({ info, melhor, economia }: { info: InfoRecalculo; melhor: string | null; economia: number | null }) {
  const economiaDe = (v: number | null) => (v ? ` (economia de ${brl(v)} por ano)` : "");
  return (
    <div role="note" className="rounded-lg border border-sky-200 bg-sky-50 px-4 py-3 text-sm text-sky-900">
      <strong className="font-medium">Recalculada com as regras atuais em {dataHora(info.em)}.</strong>{" "}
      {info.resumo ? (
        info.resumo
      ) : (
        <>
          Antes: {info.antes.melhor ?? "—"}
          {economiaDe(info.antes.economia_vs_pior)}. Agora: {melhor ?? "—"}
          {economiaDe(economia)}.
        </>
      )}{" "}
      A simulação anterior continua no histórico do cliente.
    </div>
  );
}

/** Mostra uma simulação salva com o componente certo para o seu tipo. */
export function ResultadoSimulacao({ sim, acoes }: { sim: Simulacao; acoes?: ReactNode }) {
  const recalculo = (sim.resultado as { recalculo?: InfoRecalculo }).recalculo;
  const conteudo = <ConteudoSimulacao sim={sim} acoes={acoes} />;
  if (!recalculo) return conteudo;
  const res = sim.resultado as unknown as { melhor?: string; economia_vs_pior?: number };
  return (
    <div className="flex flex-col gap-4">
      <FaixaRecalculo info={recalculo} melhor={res.melhor ?? null} economia={res.economia_vs_pior ?? null} />
      {conteudo}
    </div>
  );
}

function ConteudoSimulacao({ sim, acoes }: { sim: Simulacao; acoes?: ReactNode }) {
  const r = sim.resultado as unknown;
  switch (sim.tipo) {
    case "reforma":
      return <ResultadoReforma r={r as TReforma} acoes={acoes} />;
    case "simples_reforma":
      return <ResultadoSimplesReforma r={r as TSimplesReforma} acoes={acoes} />;
    case "autonomo":
      return <ResultadoAutonomo r={r as TAutonomo} acoes={acoes} />;
    case "pro_labore":
      return <ResultadoProLabore r={r as TProLabore} acoes={acoes} />;
    case "recuperacao":
      return <ResultadoRecuperacao r={r as TRecuperacao} acoes={acoes} />;
    default:
      return <ResultadoComparativo resultado={sim.resultado} acoes={acoes} />;
  }
}
