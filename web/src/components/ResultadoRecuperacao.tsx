"use client";

import type { ReactNode } from "react";

import { brl, competenciaCurta, numero, pct } from "@/lib/formato";
import type { ResultadoRecuperacao as TResultado } from "@/lib/tipos";

import { Destaque, Indicadores, ListaAlertas, MemoriaCalculo } from "./Blocos";
import { GraficoRecuperacao } from "./GraficoRecuperacao";
import { Cartao } from "./ui";

const th = "px-2 py-2 text-right font-medium";
const td = "px-2 py-1.5 text-right";

/** Quanto o cliente do Simples pode ter pago a mais por não segregar produtos monofásicos e com ICMS-ST. */
export function ResultadoRecuperacao({ r, acoes }: { r: TResultado; acoes?: ReactNode }) {
  const t = r.totais;
  const comValor = r.meses.filter((m) => m.calculado && (m.provavel > 0 || m.a_verificar > 0));
  const periodo = r.periodo.inicio && r.periodo.fim ? `${competenciaCurta(r.periodo.inicio)} a ${competenciaCurta(r.periodo.fim)}` : "";
  return (
    <div className="flex flex-col gap-4">
      <Destaque
        rotulo="Possível pagamento a mais no período analisado"
        titulo={brl(t.provavel)}
        sub={`${periodo} · ${r.periodo.meses} ${r.periodo.meses === 1 ? "mês" : "meses"} de notas · Anexo ${r.anexo} do Simples`}
        numeroRotulo="Economia por ano daqui para frente"
        numero={brl(r.economia_anual)}
        numeroSub="se a receita desses produtos for segregada no PGDAS-D"
        acoes={acoes}
      />
      <Indicadores
        itens={[
          { rotulo: "PIS/Cofins (produtos monofásicos)", valor: brl(t.pis_cofins), detalhe: `${brl(t.base_monofasico)} em vendas desses produtos` },
          { rotulo: "ICMS (produtos com substituição tributária)", valor: brl(t.icms), detalhe: `${brl(t.base_st)} em vendas desses produtos` },
          { rotulo: "A conferir antes de contar", valor: brl(t.a_verificar), detalhe: "lista parcial de NCM ou só com CEST" },
        ]}
      />
      <ListaAlertas alertas={r.alertas} />
      {comValor.length > 0 && (
        <Cartao titulo="Pago a mais por mês (R$)">
          <GraficoRecuperacao meses={r.meses} />
          <p className="mt-1 text-xs text-tinta-2">Últimos 12 meses importados. No topo de cada coluna (ou ao tocar nela), o total do mês.</p>
          <div className="mt-4 overflow-x-auto">
            <table className="num w-full min-w-[720px] text-[13px]">
              <thead>
                <tr className="border-b border-borda text-xs text-tinta-2">
                  <th className="py-2 pr-2 text-left font-medium">Mês</th>
                  {["Vendas do mês", "Base monofásica", "Base com ST", "Alíquota efetiva", "PIS/Cofins", "ICMS", "Total"].map((c) => (
                    <th key={c} className={th}>{c}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {[...comValor].reverse().map((m) => (
                  <tr key={m.competencia} className="border-b border-borda/70">
                    <td className="py-1.5 pr-2">{competenciaCurta(m.competencia)}</td>
                    <td className={td}>{numero(m.receita)}</td>
                    <td className={td}>{numero(m.base_monofasico)}</td>
                    <td className={td}>{numero(m.base_st)}</td>
                    <td className={td}>{pct(m.aliquota_efetiva, 2)}{m.rbt12_estimado ? "*" : ""}</td>
                    <td className={td}>{numero(m.pis_cofins)}</td>
                    <td className={td}>{numero(m.icms)}</td>
                    <td className={`${td} font-medium`}>{numero(m.provavel)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="mt-2 text-xs text-tinta-2">Valores em R$. * RBT12 estimado pela média dos meses importados.</p>
          </div>
        </Cartao>
      )}
      {r.produtos.length > 0 && (
        <Cartao titulo="Produtos identificados nas notas de venda">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[640px] text-[13px]">
              <thead>
                <tr className="border-b border-borda text-xs text-tinta-2">
                  <th className="py-2 pr-2 text-left font-medium">NCM</th>
                  <th className="px-2 py-2 text-left font-medium">Produto</th>
                  <th className="px-2 py-2 text-left font-medium">Enquadramento</th>
                  <th className={th}>Vendido (R$)</th>
                  <th className="px-2 py-2 text-left font-medium">Situação</th>
                </tr>
              </thead>
              <tbody>
                {r.produtos.map((p, i) => (
                  <tr key={`${p.ncm}-${i}`} className="border-b border-borda/70 align-top">
                    <td className="num py-1.5 pr-2">{p.ncm ?? "—"}</td>
                    <td className="px-2 py-1.5">
                      {p.descricao ?? "—"}
                      {p.grupo && (
                        <div className="text-xs text-tinta-2">
                          {p.grupo} · {p.base_legal}
                          {p.observacao ? ` — ${p.observacao}` : ""}
                        </div>
                      )}
                    </td>
                    <td className="px-2 py-1.5">{[p.monofasico, p.st].filter(Boolean).join(" · ")}</td>
                    <td className="num px-2 py-1.5 text-right">{numero(p.valor)}</td>
                    <td className="whitespace-nowrap px-2 py-1.5">
                      {p.certeza === "provavel" ? (
                        <span className="font-medium text-emerald-700">Provável</span>
                      ) : (
                        <span className="font-medium text-amber-700">Conferir</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Cartao>
      )}
      <MemoriaCalculo blocos={[{ titulo: "Como o valor foi estimado", total: brl(t.provavel), passos: r.memoria }]} />
    </div>
  );
}
