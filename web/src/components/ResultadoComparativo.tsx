"use client";

import type { ReactNode } from "react";

import { brl, pct } from "@/lib/formato";
import type { Comparativo } from "@/lib/tipos";

import { Destaque, ListaAlertas, MemoriaCalculo } from "./Blocos";
import { GraficoRegimes } from "./GraficoRegimes";
import { Cartao } from "./ui";

export function ResultadoComparativo({ resultado, acoes }: { resultado: Comparativo; acoes?: ReactNode }) {
  const aplicaveis = resultado.regimes.filter((r) => r.aplicavel);
  const melhor = aplicaveis.find((r) => r.titulo === resultado.melhor);
  const nomesTributos = Array.from(new Set(aplicaveis.flatMap((r) => r.tributos.map((t) => t.nome))));
  const destacar = (titulo: string) => (titulo === resultado.melhor ? "bg-fundo" : "");

  return (
    <div className="flex flex-col gap-4">
      <Destaque
        rotulo="Regime recomendado"
        titulo={resultado.melhor}
        sub={melhor ? `${brl(melhor.total)} por ano · carga efetiva de ${pct(melhor.carga_efetiva)}` : undefined}
        numeroRotulo={resultado.economia_vs_pior > 0 ? "Economia estimada" : undefined}
        numero={resultado.economia_vs_pior > 0 ? brl(resultado.economia_vs_pior) : undefined}
        numeroSub="por ano frente ao regime mais caro"
        acoes={acoes}
      />

      <Cartao titulo="Tributos por regime (R$/ano)">
        <GraficoRegimes regimes={resultado.regimes} melhor={resultado.melhor} />
        <div className="mt-4 overflow-x-auto">
          <table className="w-full min-w-[480px] text-sm">
            <thead>
              <tr className="border-b border-borda text-left text-xs text-tinta-2">
                <th className="py-2 pr-2 font-medium">Tributo</th>
                {aplicaveis.map((r) => (
                  <th key={r.titulo} className={`px-2 py-2 text-right font-medium ${destacar(r.titulo)}`}>
                    {r.titulo}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="num">
              {nomesTributos.map((nome) => (
                <tr key={nome} className="border-b border-borda/70">
                  <td className="py-1.5 pr-2">{nome}</td>
                  {aplicaveis.map((r) => {
                    const t = r.tributos.find((x) => x.nome === nome);
                    return (
                      <td key={r.titulo} className={`px-2 py-1.5 text-right ${destacar(r.titulo)}`}>
                        {t ? brl(t.valor) : <span className="text-tinta-2">—</span>}
                      </td>
                    );
                  })}
                </tr>
              ))}
              <tr className="font-semibold">
                <td className="py-2 pr-2">Total</td>
                {aplicaveis.map((r) => (
                  <td key={r.titulo} className={`px-2 py-2 text-right ${destacar(r.titulo)}`}>
                    {brl(r.total)}
                  </td>
                ))}
              </tr>
              <tr className="text-xs text-tinta-2">
                <td className="pr-2">Carga efetiva</td>
                {aplicaveis.map((r) => (
                  <td key={r.titulo} className={`px-2 pb-2 text-right ${destacar(r.titulo)}`}>
                    {pct(r.carga_efetiva)}
                  </td>
                ))}
              </tr>
            </tbody>
          </table>
        </div>
      </Cartao>

      <ListaAlertas alertas={[...resultado.alertas, ...resultado.regimes.flatMap((r) => r.alertas)]} />
      <MemoriaCalculo blocos={aplicaveis.map((r) => ({ titulo: r.titulo, total: brl(r.total), passos: r.memoria }))} />
    </div>
  );
}
