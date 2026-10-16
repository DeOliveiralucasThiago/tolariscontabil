"use client";

import { useEffect, useState } from "react";
import { CartesianGrid, Legend, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { api } from "@/lib/api";
import { brl, brlCurto, competenciaCurta, pct } from "@/lib/formato";
import type { Acompanhamento as Dados, CompletaEntrada, ProjecaoLimites } from "@/lib/tipos";

import { Indicadores } from "./Blocos";
import { Aviso, Botao, Cartao, Etiqueta } from "./ui";

const SERIE_REAL = "#2a78d6";
const SERIE_PROJETADA = "#eb6834";
const CAMPO_DO_PLANEJAMENTO: Record<string, keyof CompletaEntrada> = {
  receita: "receita_bruta_anual",
  compras: "compras_anual",
  folha: "folha_clt_anual",
  pro_labore: "pro_labore_anual",
  despesas_creditaveis: "despesas_creditaveis_anual",
  outras_despesas: "outras_despesas_anual",
};
const CONFIANCA = { alta: "alta", media: "média", baixa: "baixa" } as const;

function GraficoLimites({ proj }: { proj: ProjecaoLimites }) {
  const dados = proj.serie.map((p) => ({
    mes: competenciaCurta(p.competencia),
    real: p.projetado && !p.ancora ? null : p.rbt12,
    projetado: p.projetado || p.ancora ? p.rbt12 : null,
  }));
  const maior = Math.max(...proj.serie.map((p) => p.rbt12));
  // Só desenha os limites que cabem na escala do gráfico; os demais ficam no texto
  const limites = proj.limites.filter((l) => l.valor <= maior * 1.6);
  const valores = [...proj.serie.map((p) => p.rbt12), ...limites.map((l) => l.valor)];
  const teto = Math.max(...valores) * 1.08;
  const piso = Math.max(0, Math.min(...valores) * 0.8); // não começa em zero: a linha ocuparia só o topo do gráfico
  return (
    <div className="h-72 w-full" role="img" aria-label="Receita dos últimos 12 meses (RBT12) realizada e projetada, com os limites do regime">
      <ResponsiveContainer>
        <LineChart data={dados} margin={{ top: 8, right: 16, bottom: 0, left: 8 }}>
          <CartesianGrid vertical={false} stroke="var(--borda)" />
          <XAxis dataKey="mes" tickLine={false} axisLine={{ stroke: "var(--borda)" }} tick={{ fill: "var(--tinta-2)", fontSize: 12 }} interval="preserveStartEnd" minTickGap={24} />
          <YAxis domain={[piso, teto]} tickFormatter={(v: number) => brlCurto(v)} tickLine={false} axisLine={false} width={78} tick={{ fill: "var(--tinta-2)", fontSize: 11 }} />
          <Tooltip
            formatter={(v, nome) => [brl(Number(v)), nome === "real" ? "Realizado" : "Projetado"]}
            contentStyle={{ fontSize: 12, borderRadius: 8, border: "1px solid var(--borda)" }}
          />
          <Legend verticalAlign="top" align="left" height={30} iconType="plainline" wrapperStyle={{ fontSize: 12 }}
            formatter={(v: string) => <span style={{ color: "var(--tinta)" }}>{v === "real" ? "RBT12 realizado" : "RBT12 projetado"}</span>} />
          {limites.map((l) => (
            <ReferenceLine key={l.codigo} y={l.valor} stroke="var(--tinta-2)" strokeDasharray="4 4"
              label={{ value: `${l.rotulo}: ${brlCurto(l.valor)}`, position: "insideTopLeft", fill: "var(--tinta-2)", fontSize: 11 }} />
          ))}
          <Line dataKey="real" stroke={SERIE_REAL} strokeWidth={2} dot={{ r: 3 }} isAnimationActive={false} connectNulls />
          <Line dataKey="projetado" stroke={SERIE_PROJETADA} strokeWidth={2} strokeDasharray="6 4" dot={false} isAnimationActive={false} connectNulls />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

/** Planejado × realizado (últimos 12 meses), reavaliação da recomendação e projeção dos limites de enquadramento. */
export function Acompanhamento({
  clienteId,
  versao,
  onUsarNoPlanejamento,
}: {
  clienteId: number;
  versao: number;
  onUsarNoPlanejamento: (p: Partial<CompletaEntrada>, texto: string) => void;
}) {
  const [d, setD] = useState<Dados | null>(null);
  const [erro, setErro] = useState(false);

  useEffect(() => {
    api<Dados>(`/clientes/${clienteId}/acompanhamento`).then(setD).catch(() => setErro(true));
  }, [clienteId, versao]);

  if (erro) return <Aviso>Não foi possível carregar o acompanhamento.</Aviso>;
  if (!d) return null;
  if (!d.disponivel) {
    return (
      <Cartao titulo="Planejado × realizado">
        <p className="text-sm text-tinta-2">{d.motivo}</p>
      </Cartao>
    );
  }
  const re = d.reavaliacao;
  const p = d.projecao;
  const regimes = re ? Object.keys(re.totais_planejados) : [];

  function usar() {
    if (!d?.realizado_anualizado) return;
    const valores: Partial<CompletaEntrada> = {};
    for (const [campo, v] of Object.entries(d.realizado_anualizado)) {
      const destino = CAMPO_DO_PLANEJAMENTO[campo];
      if (destino && v != null) (valores as Record<string, number>)[destino] = v;
    }
    onUsarNoPlanejamento(valores, `Valores realizados de ${competenciaCurta(d.periodo!.inicio)} a ${competenciaCurta(d.periodo!.fim)} (anualizados). Confira atividade e alíquotas.`);
  }

  return (
    <div className="flex flex-col gap-4">
      <Cartao
        titulo="Planejado × realizado"
        acoes={<Botao variante="secundario" onClick={usar}>Novo planejamento com os números reais</Botao>}
      >
        <div className="flex flex-col gap-3 text-sm">
          {d.resumo.map((t) => <p key={t}>{t}</p>)}
          {!d.plano && (
            <p className="text-tinta-2">
              {d.meses! < 3
                ? "Com menos de 3 meses de dados ainda não dá para comparar com o planejamento."
                : "Este cliente ainda não tem um planejamento (expresso ou completo) para comparar."}
            </p>
          )}
          {d.plano && !re && d.meses! < 6 && (
            <p className="text-tinta-2">Com 6 meses ou mais de dados, o comparativo de regimes é refeito com os números reais.</p>
          )}
          {d.plano && <p className="text-xs text-tinta-2">Planejamento usado: {d.plano.titulo}.</p>}
        </div>
      </Cartao>

      {re && (
        <Cartao titulo="A recomendação ainda vale?" acoes={<Etiqueta tom={re.mudou ? "prospect" : "ativo"}>{re.mudou ? "Mudou" : "Mantida"}</Etiqueta>}>
          <div className="flex flex-col gap-3 text-sm">
            <p>
              {re.mudou ? (
                <>Com os números reais, a melhor opção passou de <strong>{re.melhor_planejado}</strong> para <strong>{re.melhor_realizado}</strong>.</>
              ) : (
                <>Com os números reais, a melhor opção continua <strong>{re.melhor_realizado}</strong>.</>
              )}
              {re.economia_realizada != null && <> Economia de {brl(re.economia_realizada)} por ano em relação à pior opção (no planejamento: {brl(re.economia_planejada)}).</>}
            </p>
            <div className="overflow-x-auto">
              <table className="num w-full min-w-[420px] text-[13px]">
                <thead>
                  <tr className="border-b border-borda text-xs text-tinta-2">
                    <th className="py-2 pr-2 text-left font-medium">Regime</th>
                    <th className="px-2 py-2 text-right font-medium">Custo no planejamento</th>
                    <th className="px-2 py-2 text-right font-medium">Custo com o realizado</th>
                  </tr>
                </thead>
                <tbody>
                  {regimes.map((r) => (
                    <tr key={r} className="border-b border-borda/70">
                      <td className="py-1.5 pr-2">{r}</td>
                      <td className="px-2 py-1.5 text-right">{brl(re.totais_planejados[r])}</td>
                      <td className="px-2 py-1.5 text-right">{brl(re.totais_realizados[r])}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {d.fator_r && (
              <div className="rounded-lg bg-fundo px-3 py-2">
                <div className="font-medium">{d.fator_r.titulo}</div>
                <div className="text-xs text-tinta-2">{d.fator_r.detalhe}</div>
              </div>
            )}
          </div>
        </Cartao>
      )}

      {d.comparacao.length > 0 && (
        <Cartao titulo="Números do período">
          <div className="overflow-x-auto">
            <table className="num w-full min-w-[520px] text-[13px]">
              <thead>
                <tr className="border-b border-borda text-xs text-tinta-2">
                  <th className="py-2 pr-2 text-left font-medium">Item (por ano)</th>
                  <th className="px-2 py-2 text-right font-medium">Planejado</th>
                  <th className="px-2 py-2 text-right font-medium">Realizado*</th>
                  <th className="px-2 py-2 text-right font-medium">Diferença</th>
                </tr>
              </thead>
              <tbody>
                {d.comparacao.map((l) => (
                  <tr key={l.campo} className="border-b border-borda/70">
                    <td className="py-1.5 pr-2">{l.rotulo}</td>
                    <td className="px-2 py-1.5 text-right">{brl(l.planejado)}</td>
                    <td className="px-2 py-1.5 text-right">{l.realizado == null ? "—" : brl(l.realizado)}</td>
                    <td className="px-2 py-1.5 text-right">
                      {l.diferenca == null ? "—" : `${l.diferenca >= 0 ? "+" : "−"}${brl(Math.abs(l.diferenca))}${l.diferenca_pct == null ? "" : ` (${l.diferenca >= 0 ? "+" : "−"}${pct(Math.abs(l.diferenca_pct), 0)})`}`}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="mt-2 text-xs text-tinta-2">
              * Últimos {d.meses} {d.meses === 1 ? "mês" : "meses"} com receita ({competenciaCurta(d.periodo!.inicio)} a {competenciaCurta(d.periodo!.fim)}),
              anualizados. Receita e compras vêm da planilha contábil e, na falta dela, das notas; o restante, só da planilha. “—” = sem dado.
            </p>
          </div>
        </Cartao>
      )}

      {p ? (
        <Cartao titulo="Projeção dos limites">
          <div className="flex flex-col gap-4 text-sm">
            <Indicadores
              itens={[
                { rotulo: "RBT12 hoje", valor: brl(p.rbt12_atual) },
                { rotulo: "RBT12 em 12 meses (no ritmo atual)", valor: brl(p.rbt12_em_12_meses) },
                { rotulo: "Tendência da receita", valor: `${p.tendencia_mensal >= 0 ? "+" : "−"}${brl(Math.abs(p.tendencia_mensal))}/mês`, detalhe: `Confiança ${CONFIANCA[p.confianca]} · ${p.meses_base} meses` },
              ]}
            />
            {p.cruzamentos.length > 0 ? (
              <ul className="flex flex-col gap-1">
                {p.cruzamentos.map((c) => (
                  <li key={c.codigo} className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-amber-900">
                    No ritmo atual, o cliente passa do <strong>{c.rotulo}</strong> ({brl(c.limite)}) em <strong>{competenciaCurta(c.competencia)}</strong>, daqui a {c.em_meses} {c.em_meses === 1 ? "mês" : "meses"}.
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-tinta-2">
                {p.limites.length ? "Nenhum limite de enquadramento é ultrapassado nos próximos 12 meses no ritmo atual." : "Defina o regime atual do cliente (aba Dados cadastrais) para ver os limites."}
              </p>
            )}
            <GraficoLimites proj={p} />
            <p className="text-xs text-tinta-2">
              Projeção linear da receita dos últimos {p.meses_base} meses, não uma previsão: sazonalidade, contratos novos e perdas mudam o ritmo.
              {p.confianca === "baixa" && " A confiança é baixa (poucos meses ou receita muito irregular): use só como referência."}
            </p>
          </div>
        </Cartao>
      ) : (
        <Cartao titulo="Projeção dos limites">
          <p className="text-sm text-tinta-2">São necessários ao menos 6 meses de receita para projetar o ritmo e os limites.</p>
        </Cartao>
      )}
    </div>
  );
}
