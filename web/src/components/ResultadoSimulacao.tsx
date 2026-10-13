"use client";

import type { ReactNode } from "react";

import type {
  ResultadoAutonomo as TAutonomo,
  ResultadoProLabore as TProLabore,
  ResultadoRecuperacao as TRecuperacao,
  ResultadoReforma as TReforma,
  ResultadoSimplesReforma as TSimplesReforma,
  Simulacao,
} from "@/lib/tipos";

import { ResultadoComparativo } from "./ResultadoComparativo";
import { ResultadoRecuperacao } from "./ResultadoRecuperacao";
import { ResultadoAutonomo, ResultadoProLabore, ResultadoReforma, ResultadoSimplesReforma } from "./ResultadosFase2";

/** Mostra uma simulação salva com o componente certo para o seu tipo. */
export function ResultadoSimulacao({ sim, acoes }: { sim: Simulacao; acoes?: ReactNode }) {
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
