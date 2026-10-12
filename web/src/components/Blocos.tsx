"use client";

import { brl, pct } from "@/lib/formato";
import type { PassoMemoria } from "@/lib/tipos";

import { Aviso, Cartao } from "./ui";

const ehTaxa = (p: PassoMemoria) => /alíquota|fator r|percentua|fatia/i.test(p.descricao);

export function ListaAlertas({ alertas, titulo = "Pontos de atenção" }: { alertas: string[]; titulo?: string }) {
  const unicos = Array.from(new Set(alertas));
  if (!unicos.length) return null;
  return (
    <Cartao titulo={titulo}>
      <ul className="flex flex-col gap-2">
        {unicos.map((a) => (
          <li key={a}>
            <Aviso>{a}</Aviso>
          </li>
        ))}
      </ul>
    </Cartao>
  );
}

export function MemoriaCalculo({ blocos }: { blocos: { titulo: string; total?: string; passos: PassoMemoria[] }[] }) {
  return (
    <Cartao titulo="Memória de cálculo">
      <div className="flex flex-col gap-2">
        {blocos.map((b) => (
          <details key={b.titulo} className="group rounded-lg border border-borda">
            <summary className="flex cursor-pointer list-none items-center justify-between px-4 py-3 text-sm font-medium">
              <span>{b.titulo}</span>
              <span className="num text-tinta-2">
                {b.total} <span className="ml-2 inline-block transition group-open:rotate-90">›</span>
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
                  {b.passos.map((p, i) => (
                    <tr key={i} className="border-t border-borda/70 align-top">
                      <td className="px-4 py-1.5">{p.descricao}</td>
                      <td className="px-2 py-1.5 text-tinta-2">{p.formula}</td>
                      <td className="num whitespace-nowrap px-2 py-1.5 text-right">{ehTaxa(p) ? pct(p.valor, 4) : brl(p.valor)}</td>
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
  );
}

/** Cabeçalho de resultado: título em destaque, número-chave e ações (salvar, PDF). */
export function Destaque({
  rotulo,
  titulo,
  sub,
  numeroRotulo,
  numero,
  numeroSub,
  acoes,
}: {
  rotulo: string;
  titulo: string;
  sub?: string;
  numeroRotulo?: string;
  numero?: string;
  numeroSub?: string;
  acoes?: React.ReactNode;
}) {
  return (
    <section className="rounded-xl border-2 border-marca bg-superficie p-5">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="text-xs font-medium uppercase tracking-wide text-tinta-2">{rotulo}</div>
          <div className="mt-1 text-2xl font-semibold">{titulo}</div>
          {sub && <div className="num mt-1 text-sm text-tinta-2">{sub}</div>}
        </div>
        {numero && (
          <div className="ml-auto text-right">
            {numeroRotulo && <div className="text-xs font-medium uppercase tracking-wide text-tinta-2">{numeroRotulo}</div>}
            <div className="num text-3xl font-semibold text-marca">{numero}</div>
            {numeroSub && <div className="text-xs text-tinta-2">{numeroSub}</div>}
          </div>
        )}
      </div>
      {acoes && <div className="mt-4 flex flex-wrap gap-2">{acoes}</div>}
    </section>
  );
}

export function Indicadores({ itens }: { itens: { rotulo: string; valor: string; detalhe?: string }[] }) {
  return (
    <div className="grid gap-3 sm:grid-cols-3">
      {itens.map((i) => (
        <div key={i.rotulo} className="rounded-xl border border-borda bg-superficie px-4 py-3">
          <div className="text-xs text-tinta-2">{i.rotulo}</div>
          <div className="num mt-0.5 text-lg font-semibold">{i.valor}</div>
          {i.detalhe && <div className="text-xs text-tinta-2">{i.detalhe}</div>}
        </div>
      ))}
    </div>
  );
}
