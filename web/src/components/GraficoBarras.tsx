"use client";

import { Bar, BarChart, Cell, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { brl, brlCurto } from "@/lib/formato";

export interface ItemBarra {
  rotulo: string;
  valor: number;
  destaque?: boolean;
  detalhe?: string;
}

/**
 * Barras horizontais de uma única medida. O item em destaque usa a cor do escritório;
 * os demais, um neutro (ênfase, não identidade). Itens não aplicáveis vão em nota abaixo.
 */
export function GraficoBarras({
  itens,
  naoAplicaveis = [],
  descricao,
  larguraRotulo = 170,
}: {
  itens: ItemBarra[];
  naoAplicaveis?: string[];
  descricao: string;
  larguraRotulo?: number;
}) {
  const altura = 36 + itens.length * 40;
  return (
    <div>
      <div className="w-full" style={{ height: altura }} role="img" aria-label={descricao}>
        <ResponsiveContainer>
          <BarChart data={itens} layout="vertical" margin={{ top: 4, right: 90, bottom: 4, left: 8 }} barCategoryGap={14}>
            <XAxis type="number" hide domain={[0, "dataMax"]} />
            <YAxis
              type="category"
              dataKey="rotulo"
              width={larguraRotulo}
              tickLine={false}
              axisLine={{ stroke: "var(--borda)" }}
              tick={{ fill: "var(--tinta)", fontSize: 13 }}
            />
            <Tooltip
              cursor={{ fill: "var(--fundo)" }}
              content={({ active, payload }) => {
                if (!active || !payload?.length) return null;
                const d = payload[0].payload as ItemBarra;
                return (
                  <div className="rounded-lg border border-borda bg-superficie px-3 py-2 text-xs shadow-sm">
                    <div className="font-semibold">{d.rotulo}</div>
                    <div className="num">{brl(d.valor)}</div>
                    {d.detalhe && <div className="text-tinta-2">{d.detalhe}</div>}
                  </div>
                );
              }}
            />
            <Bar dataKey="valor" radius={[0, 4, 4, 0]} isAnimationActive={false}>
              {itens.map((d) => (
                <Cell key={d.rotulo} fill={d.destaque ? "var(--marca)" : "var(--neutro)"} />
              ))}
              <LabelList
                dataKey="valor"
                position="right"
                formatter={(v: number) => brlCurto(v)}
                style={{ fill: "var(--tinta)", fontSize: 12, fontVariantNumeric: "tabular-nums" }}
              />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
      {naoAplicaveis.length > 0 && <p className="mt-1 text-xs text-tinta-2">Não aplicável: {naoAplicaveis.join(", ")}.</p>}
    </div>
  );
}
