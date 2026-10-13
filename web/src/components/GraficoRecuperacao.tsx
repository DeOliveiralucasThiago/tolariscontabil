"use client";

import { useEffect, useState } from "react";
import { Bar, BarChart, CartesianGrid, LabelList, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { brl, brlCurto, competenciaCurta } from "@/lib/formato";
import type { MesRecuperacao } from "@/lib/tipos";

// Paleta categórica validada (slots 1 e 2): identidade das duas séries
const SERIE_PIS_COFINS = "#2a78d6";
const SERIE_ICMS = "#eb6834";

function useTelaEstreita(limite = 640) {
  const [estreita, setEstreita] = useState(false);
  useEffect(() => {
    const mq = window.matchMedia(`(max-width: ${limite}px)`);
    const atualizar = () => setEstreita(mq.matches);
    atualizar();
    mq.addEventListener("change", atualizar);
    return () => mq.removeEventListener("change", atualizar);
  }, [limite]);
  return estreita;
}

/** R$ 432 (sem centavos, o gráfico é uma visão geral) ou R$ 1,2 mil. */
const reais = (v: number) => (v >= 1000 ? brlCurto(v) : `R$ ${Math.round(v)}`);
/** Rótulo no topo da coluna: sem "R$" (o eixo já diz) para caber sobre a barra estreita. */
const compacto = new Intl.NumberFormat("pt-BR", { notation: "compact", maximumFractionDigits: 1 });

/** Eixo com 4 intervalos iguais e de valor "redondo" (R$ 150, 300, 450, 600), com folga para o rótulo do topo. */
function eixo(max: number): number[] {
  if (max <= 0) return [0, 25, 50, 75, 100];
  const alvo = (max * 1.15) / 4;
  const base = 10 ** Math.floor(Math.log10(alvo));
  const passo = [1, 1.5, 2, 2.5, 3, 4, 5, 10].map((f) => f * base).find((v) => v >= alvo) ?? alvo;
  return [0, 1, 2, 3, 4].map((i) => i * passo);
}

/** Colunas empilhadas por mês (últimos 12): PIS/Cofins × ICMS pagos a mais, com o total no topo. */
export function GraficoRecuperacao({ meses }: { meses: MesRecuperacao[] }) {
  const estreita = useTelaEstreita();
  const dados = meses.slice(-12).map((m) => ({ ...m, mes: competenciaCurta(m.competencia) }));
  const ticks = eixo(Math.max(0, ...dados.map((d) => d.provavel)));
  return (
    <div className="h-72 w-full" role="img" aria-label="Valor pago a mais por mês, separado em PIS/Cofins e ICMS">
      <ResponsiveContainer>
        <BarChart data={dados} margin={{ top: 8, right: 8, bottom: 0, left: 8 }} barCategoryGap="24%">
          <CartesianGrid vertical={false} stroke="var(--borda)" />
          <XAxis dataKey="mes" tickLine={false} axisLine={{ stroke: "var(--borda)" }} tick={{ fill: "var(--tinta-2)", fontSize: 12 }} interval={estreita ? 2 : 0} />
          <YAxis
            tickFormatter={reais}
            tickLine={false}
            axisLine={false}
            width={72}
            domain={[0, ticks[4]]}
            ticks={ticks}
            tick={{ fill: "var(--tinta-2)", fontSize: 11 }}
          />
          <Tooltip
            cursor={{ fill: "var(--fundo)" }}
            content={({ active, payload }) => {
              if (!active || !payload?.length) return null;
              const d = payload[0].payload as (typeof dados)[number];
              return (
                <div className="rounded-lg border border-borda bg-superficie px-3 py-2 text-xs shadow-sm">
                  <div className="font-semibold">{d.mes}</div>
                  <div className="num">PIS/Cofins: {brl(d.pis_cofins)}</div>
                  <div className="num">ICMS: {brl(d.icms)}</div>
                  <div className="num font-medium">Total: {brl(d.provavel)}</div>
                </div>
              );
            }}
          />
          <Legend
            verticalAlign="top"
            align="left"
            height={estreita ? 52 : 30}
            iconType="square"
            wrapperStyle={{ fontSize: 12 }}
            formatter={(valor: string) => <span style={{ color: "var(--tinta)" }}>{valor}</span>}
          />
          <Bar dataKey="pis_cofins" name="PIS/Cofins (monofásico)" stackId="t" fill={SERIE_PIS_COFINS} stroke="var(--superficie)" strokeWidth={2} isAnimationActive={false} />
          <Bar dataKey="icms" name="ICMS (substituição tributária)" stackId="t" fill={SERIE_ICMS} stroke="var(--superficie)" strokeWidth={2} radius={[4, 4, 0, 0]} isAnimationActive={false}>
            {!estreita && (
              <LabelList
                dataKey="provavel"
                position="top"
                formatter={(v: number) => (v > 0 ? compacto.format(v >= 1000 ? v : Math.round(v)) : "")}
                style={{ fill: "var(--tinta)", fontSize: 11, fontVariantNumeric: "tabular-nums" }}
              />
            )}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
