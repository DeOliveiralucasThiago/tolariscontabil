"use client";

import { pct } from "@/lib/formato";
import type { ResultadoRegime } from "@/lib/tipos";

import { GraficoBarras } from "./GraficoBarras";

/** Total anual por regime; o recomendado na cor do escritório. */
export function GraficoRegimes({ regimes, melhor }: { regimes: ResultadoRegime[]; melhor: string }) {
  return (
    <GraficoBarras
      descricao={`Total anual de tributos por regime; recomendado: ${melhor}`}
      itens={regimes
        .filter((r) => r.aplicavel)
        .map((r) => ({
          rotulo: r.titulo,
          valor: r.total,
          destaque: r.titulo === melhor,
          detalhe: `Carga efetiva: ${pct(r.carga_efetiva)}`,
        }))}
      naoAplicaveis={regimes.filter((r) => !r.aplicavel).map((r) => r.titulo)}
      larguraRotulo={150}
    />
  );
}
