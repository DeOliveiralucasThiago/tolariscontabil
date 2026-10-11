"use client";

import { Bar, BarChart, Cell, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { brl, brlCurto, pct } from "@/lib/formato";
import type { ResultadoRegime } from "@/lib/tipos";

/**
 * Total anual por regime em barras horizontais. Uma única série: o regime recomendado
 * recebe a cor do escritório e os demais um neutro (ênfase, não identidade).
 */
export function GraficoRegimes({ regimes, melhor }: { regimes: ResultadoRegime[]; melhor: string }) {
  const dados = regimes
    .filter((r) => r.aplicavel)
    .map((r) => ({ regime: r.titulo, total: r.total, carga: r.carga_efetiva, melhor: r.titulo === melhor }));
  const naoAplicaveis = regimes.filter((r) => !r.aplicavel);

  return (
    <div>
      <div className="h-44 w-full" role="img" aria-label={`Total anual de tributos por regime; recomendado: ${melhor}`}>
        <ResponsiveContainer>
          <BarChart data={dados} layout="vertical" margin={{ top: 4, right: 90, bottom: 4, left: 8 }} barCategoryGap={14}>
            <XAxis type="number" hide domain={[0, "dataMax"]} />
            <YAxis
              type="category"
              dataKey="regime"
              width={150}
              tickLine={false}
              axisLine={{ stroke: "var(--borda)" }}
              tick={{ fill: "var(--tinta)", fontSize: 13 }}
            />
            <Tooltip
              cursor={{ fill: "var(--fundo)" }}
              content={({ active, payload }) => {
                if (!active || !payload?.length) return null;
                const d = payload[0].payload as (typeof dados)[number];
                return (
                  <div className="rounded-lg border border-borda bg-superficie px-3 py-2 text-xs shadow-sm">
                    <div className="font-semibold">{d.regime}</div>
                    <div className="num">{brl(d.total)} por ano</div>
                    <div className="num text-tinta-2">Carga efetiva: {pct(d.carga)}</div>
                  </div>
                );
              }}
            />
            <Bar dataKey="total" radius={[0, 4, 4, 0]} isAnimationActive={false}>
              {dados.map((d) => (
                <Cell key={d.regime} fill={d.melhor ? "var(--marca)" : "var(--neutro)"} />
              ))}
              <LabelList
                dataKey="total"
                position="right"
                formatter={(v: number) => brlCurto(v)}
                style={{ fill: "var(--tinta)", fontSize: 12, fontVariantNumeric: "tabular-nums" }}
              />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
      {naoAplicaveis.length > 0 && (
        <p className="mt-1 text-xs text-tinta-2">
          Não aplicável: {naoAplicaveis.map((r) => r.titulo).join(", ")}.
        </p>
      )}
    </div>
  );
}
