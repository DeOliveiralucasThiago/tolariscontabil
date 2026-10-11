"use client";

import type { ReactNode } from "react";

import { brl, pct } from "@/lib/formato";
import type { Comparativo, PassoMemoria } from "@/lib/tipos";

import { GraficoRegimes } from "./GraficoRegimes";
import { Aviso, Cartao } from "./ui";

const ehTaxa = (p: PassoMemoria) => /^(Alíquota|Fator R|Percentuais)/.test(p.descricao);

export function ResultadoComparativo({ resultado, acoes }: { resultado: Comparativo; acoes?: ReactNode }) {
  const aplicaveis = resultado.regimes.filter((r) => r.aplicavel);
  const melhor = aplicaveis.find((r) => r.titulo === resultado.melhor);
  const nomesTributos = Array.from(new Set(aplicaveis.flatMap((r) => r.tributos.map((t) => t.nome))));
  const alertas = Array.from(new Set([...resultado.alertas, ...resultado.regimes.flatMap((r) => r.alertas)]));

  return (
    <div className="flex flex-col gap-4">
      <section className="rounded-xl border-2 border-marca bg-superficie p-5">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="text-xs font-medium uppercase tracking-wide text-tinta-2">Regime recomendado</div>
            <div className="mt-1 text-2xl font-semibold">{resultado.melhor}</div>
            {melhor && (
              <div className="mt-1 text-sm text-tinta-2 num">
                {brl(melhor.total)} por ano · carga efetiva de {pct(melhor.carga_efetiva)}
              </div>
            )}
          </div>
          {resultado.economia_vs_pior > 0 && (
            <div className="text-right">
              <div className="text-xs font-medium uppercase tracking-wide text-tinta-2">Economia estimada</div>
              <div className="num text-3xl font-semibold text-marca">{brl(resultado.economia_vs_pior)}</div>
              <div className="text-xs text-tinta-2">por ano frente ao regime mais caro</div>
            </div>
          )}
        </div>
        {acoes && <div className="mt-4 flex flex-wrap gap-2">{acoes}</div>}
      </section>

      <Cartao titulo="Tributos por regime (R$/ano)">
        <GraficoRegimes regimes={resultado.regimes} melhor={resultado.melhor} />
        <div className="mt-4 overflow-x-auto">
          <table className="w-full min-w-[480px] text-sm">
            <thead>
              <tr className="border-b border-borda text-left text-xs text-tinta-2">
                <th className="py-2 pr-2 font-medium">Tributo</th>
                {aplicaveis.map((r) => (
                  <th
                    key={r.titulo}
                    className={`py-2 px-2 text-right font-medium ${r.titulo === resultado.melhor ? "bg-fundo text-tinta" : ""}`}
                  >
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
                      <td key={r.titulo} className={`py-1.5 px-2 text-right ${r.titulo === resultado.melhor ? "bg-fundo" : ""}`}>
                        {t ? brl(t.valor) : <span className="text-tinta-2">—</span>}
                      </td>
                    );
                  })}
                </tr>
              ))}
              <tr className="font-semibold">
                <td className="py-2 pr-2">Total</td>
                {aplicaveis.map((r) => (
                  <td key={r.titulo} className={`py-2 px-2 text-right ${r.titulo === resultado.melhor ? "bg-fundo" : ""}`}>
                    {brl(r.total)}
                  </td>
                ))}
              </tr>
              <tr className="text-xs text-tinta-2">
                <td className="pr-2">Carga efetiva</td>
                {aplicaveis.map((r) => (
                  <td key={r.titulo} className={`px-2 pb-2 text-right ${r.titulo === resultado.melhor ? "bg-fundo" : ""}`}>
                    {pct(r.carga_efetiva)}
                  </td>
                ))}
              </tr>
            </tbody>
          </table>
        </div>
      </Cartao>

      {alertas.length > 0 && (
        <Cartao titulo="Pontos de atenção">
          <ul className="flex flex-col gap-2">
            {alertas.map((a) => (
              <li key={a}>
                <Aviso>{a}</Aviso>
              </li>
            ))}
          </ul>
        </Cartao>
      )}

      <Cartao titulo="Memória de cálculo">
        <div className="flex flex-col gap-2">
          {aplicaveis.map((r) => (
            <details key={r.titulo} className="group rounded-lg border border-borda">
              <summary className="flex cursor-pointer list-none items-center justify-between px-4 py-3 text-sm font-medium">
                <span>{r.titulo}</span>
                <span className="num text-tinta-2">
                  {brl(r.total)} <span className="ml-2 inline-block transition group-open:rotate-90">›</span>
                </span>
              </summary>
              <div className="overflow-x-auto border-t border-borda">
                <table className="w-full min-w-[640px] text-xs">
                  <thead>
                    <tr className="text-left text-tinta-2">
                      <th className="px-4 py-2 font-medium">Passo</th>
                      <th className="px-2 py-2 font-medium">Fórmula</th>
                      <th className="px-2 py-2 text-right font-medium">Valor</th>
                      <th className="px-4 py-2 font-medium">Base legal</th>
                    </tr>
                  </thead>
                  <tbody>
                    {r.memoria.map((p, i) => (
                      <tr key={i} className="border-t border-borda/70 align-top">
                        <td className="px-4 py-1.5">{p.descricao}</td>
                        <td className="px-2 py-1.5 text-tinta-2">{p.formula}</td>
                        <td className="num whitespace-nowrap px-2 py-1.5 text-right">
                          {ehTaxa(p) ? pct(p.valor, 4) : brl(p.valor)}
                        </td>
                        <td className="px-4 py-1.5 text-tinta-2">{p.base_legal}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </details>
          ))}
        </div>
      </Cartao>
    </div>
  );
}
