"use client";

import { useEffect, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  LabelList,
  Legend,
  Line,
  LineChart,
  ReferenceDot,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { brl, brlCurto, pct } from "@/lib/formato";
import type { AnoReforma } from "@/lib/tipos";

// Paleta categórica validada (slots 1 e 2): identidade das duas séries
const SERIE_ATUAIS = "#2a78d6";
const SERIE_NOVOS = "#eb6834";

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

/** Colunas empilhadas por ano: tributos atuais × CBS/IBS, com a carga no topo (só em telas largas). */
export function GraficoTransicao({ anos }: { anos: AnoReforma[] }) {
  const estreita = useTelaEstreita();
  const dados = anos.map((a) => ({ ano: String(a.ano), atuais: a.atuais, novos: a.novos, carga: a.carga, total: a.total }));
  return (
    <div className="h-72 w-full" role="img" aria-label="Tributos sobre o consumo por ano, de 2025 a 2033">
      <ResponsiveContainer>
        <BarChart data={dados} margin={{ top: 8, right: 8, bottom: 0, left: 8 }} barCategoryGap="28%">
          <CartesianGrid vertical={false} stroke="var(--borda)" />
          <XAxis dataKey="ano" tickLine={false} axisLine={{ stroke: "var(--borda)" }} tick={{ fill: "var(--tinta-2)", fontSize: 12 }} />
          <YAxis
            tickFormatter={(v: number) => brlCurto(v)}
            tickLine={false}
            axisLine={false}
            width={78}
            domain={[0, (max: number) => max * 1.12]}
            tick={{ fill: "var(--tinta-2)", fontSize: 11 }}
          />
          <Tooltip
            cursor={{ fill: "var(--fundo)" }}
            content={({ active, payload }) => {
              if (!active || !payload?.length) return null;
              const d = payload[0].payload as (typeof dados)[number];
              return (
                <div className="rounded-lg border border-borda bg-superficie px-3 py-2 text-xs shadow-sm">
                  <div className="font-semibold">{d.ano}</div>
                  <div className="num">Tributos atuais: {brl(d.atuais)}</div>
                  <div className="num">CBS + IBS: {brl(d.novos)}</div>
                  <div className="num font-medium">Total: {brl(d.total)} · carga {pct(d.carga)}</div>
                </div>
              );
            }}
          />
          <Legend
            verticalAlign="top"
            align="left"
            height={estreita ? 48 : 36}
            iconType="square"
            wrapperStyle={{ fontSize: 12 }}
            formatter={(valor: string) => <span style={{ color: "var(--tinta)" }}>{valor}</span>}
          />
          <Bar dataKey="atuais" name="Tributos atuais (PIS/Cofins, IPI, ICMS/ISS)" stackId="t" fill={SERIE_ATUAIS} stroke="var(--superficie)" strokeWidth={2} isAnimationActive={false} />
          <Bar dataKey="novos" name="CBS + IBS" stackId="t" fill={SERIE_NOVOS} stroke="var(--superficie)" strokeWidth={2} radius={[4, 4, 0, 0]} isAnimationActive={false}>
            {!estreita && (
              <LabelList
                dataKey="carga"
                position="top"
                formatter={(v: number) => pct(v, 1)}
                style={{ fill: "var(--tinta)", fontSize: 11, fontVariantNumeric: "tabular-nums" }}
              />
            )}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

/** Ganho de recolher IBS/CBS por fora conforme a fatia de vendas a empresas. */
export function GraficoCurvaB2B({
  pontos,
  atual,
}: {
  pontos: { b2b: number; diferenca: number }[];
  atual: { b2b: number; diferenca: number };
}) {
  const dados = pontos.map((p) => ({ b2b: Math.round(p.b2b * 100), diferenca: p.diferenca }));
  return (
    <div className="h-64 w-full" role="img" aria-label="Diferença anual entre recolher por fora e dentro do DAS por percentual de vendas B2B">
      <ResponsiveContainer>
        <LineChart data={dados} margin={{ top: 12, right: 16, bottom: 16, left: 8 }}>
          <CartesianGrid stroke="var(--borda)" vertical={false} />
          <XAxis
            dataKey="b2b"
            type="number"
            domain={[0, 100]}
            ticks={[0, 20, 40, 60, 80, 100]}
            tickFormatter={(v: number) => `${v}%`}
            tickLine={false}
            axisLine={{ stroke: "var(--borda)" }}
            tick={{ fill: "var(--tinta-2)", fontSize: 12 }}
            label={{ value: "Vendas a empresas (B2B)", position: "insideBottom", offset: -10, fill: "var(--tinta-2)", fontSize: 12 }}
          />
          <YAxis
            tickFormatter={(v: number) => brlCurto(v)}
            tickLine={false}
            axisLine={false}
            width={78}
            tick={{ fill: "var(--tinta-2)", fontSize: 11 }}
          />
          <ReferenceLine y={0} stroke="var(--tinta-2)" strokeDasharray="4 4" />
          <Tooltip
            content={({ active, payload }) => {
              if (!active || !payload?.length) return null;
              const d = payload[0].payload as (typeof dados)[number];
              return (
                <div className="rounded-lg border border-borda bg-superficie px-3 py-2 text-xs shadow-sm">
                  <div className="font-semibold">{d.b2b}% das vendas a empresas</div>
                  <div className="num">
                    {d.diferenca >= 0 ? "Por fora rende " : "No DAS rende "}
                    {brl(Math.abs(d.diferenca))} a mais por ano
                  </div>
                </div>
              );
            }}
          />
          <Line type="linear" dataKey="diferenca" stroke={SERIE_ATUAIS} strokeWidth={2} dot={false} activeDot={{ r: 5 }} isAnimationActive={false} />
          <ReferenceDot
            x={Math.round(atual.b2b * 100)}
            y={atual.diferenca}
            r={6}
            fill="var(--marca)"
            stroke="var(--superficie)"
            strokeWidth={2}
            label={{ value: "hoje", position: "top", fill: "var(--tinta)", fontSize: 11 }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
