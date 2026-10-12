"use client";

import { useState, type ReactNode } from "react";

import { brl, numero, pct } from "@/lib/formato";
import type {
  ResultadoAutonomo as TResultadoAutonomo,
  ResultadoProLabore as TResultadoProLabore,
  ResultadoReforma as TResultadoReforma,
  ResultadoSalario as TResultadoSalario,
  ResultadoSimplesReforma as TResultadoSimplesReforma,
} from "@/lib/tipos";

import { Destaque, Indicadores, ListaAlertas, MemoriaCalculo } from "./Blocos";
import { GraficoBarras } from "./GraficoBarras";
import { GraficoCurvaB2B, GraficoTransicao } from "./GraficosReforma";
import { Cartao } from "./ui";

const th = "px-2 py-2 text-right font-medium";
const td = "px-2 py-1.5 text-right";

export function ResultadoReforma({ r, acoes }: { r: TResultadoReforma; acoes?: ReactNode }) {
  const [a0, an] = [r.anos[0], r.anos[r.anos.length - 1]];
  const valor = (a: TResultadoReforma["anos"][number], nome: string) => a.tributos.find((t) => t.nome === nome)?.valor ?? 0;
  const aumento = r.variacao_total > 0;
  return (
    <div className="flex flex-col gap-4">
      <Destaque
        rotulo={`Carga sobre o consumo em ${an.ano}`}
        titulo={pct(an.carga)}
        sub={`Hoje (${a0.ano}): ${pct(a0.carga)} sobre as vendas sem tributos`}
        numeroRotulo={aumento ? "Aumento por ano" : "Redução por ano"}
        numero={brl(Math.abs(r.variacao_total))}
        numeroSub={`${an.ano} frente a ${a0.ano}`}
        acoes={acoes}
      />
      <Indicadores
        itens={[
          { rotulo: "Vendas sem tributos", valor: brl(r.base_venda) },
          { rotulo: "Aquisições com crédito", valor: brl(r.base_credito) },
          { rotulo: "CBS + IBS de referência", valor: pct(r.cbs_referencia + r.ibs_referencia, 1), detalhe: "estimativa até a fixação oficial" },
        ]}
      />
      <Cartao titulo="Tributos sobre o consumo por ano (R$)">
        <GraficoTransicao anos={r.anos} />
        <p className="mt-1 text-xs text-tinta-2">No topo (ou ao tocar na coluna), a carga sobre o valor das vendas sem tributos. Em 2026, CBS e IBS de teste são dispensados.</p>
        <div className="mt-4 overflow-x-auto">
          <table className="num w-full min-w-[600px] text-[13px]">
            <thead>
              <tr className="border-b border-borda text-xs text-tinta-2">
                <th className="py-2 pr-2 text-left font-medium">Ano</th>
                {["PIS/Cofins", "IPI", "ICMS/ISS", "CBS", "IBS", "Total", "Carga"].map((c) => (
                  <th key={c} className={th}>{c}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {r.anos.map((a) => (
                <tr key={a.ano} className="border-b border-borda/70">
                  <td className="py-1.5 pr-2">{a.ano}</td>
                  <td className={td}>{numero(valor(a, "PIS/Cofins"))}</td>
                  <td className={td}>{numero(valor(a, "IPI"))}</td>
                  <td className={td}>{numero(valor(a, "ICMS") + valor(a, "ISS"))}</td>
                  <td className={td}>{numero(valor(a, "CBS"))}</td>
                  <td className={td}>{numero(valor(a, "IBS"))}</td>
                  <td className={`${td} font-semibold`}>{numero(a.total)}</td>
                  <td className={td}>{pct(a.carga)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Cartao>
      <ListaAlertas alertas={[...r.alertas, ...r.anos.flatMap((a) => a.alertas)]} />
      <MemoriaCalculo blocos={r.anos.map((a) => ({ titulo: String(a.ano), total: brl(a.total), passos: a.memoria }))} />
    </div>
  );
}

export function ResultadoSimplesReforma({ r, acoes }: { r: TResultadoSimplesReforma; acoes?: ReactNode }) {
  const anos = r.cenarios.map((c) => String(c.ano));
  const [anoCurva, setAnoCurva] = useState(anos[anos.length - 1]);
  const final = r.cenarios[r.cenarios.length - 1];
  const cenarioCurva = r.cenarios.find((c) => String(c.ano) === anoCurva) ?? final;
  return (
    <div className="flex flex-col gap-4">
      <Destaque
        rotulo={`Recomendação para ${final.ano}`}
        titulo={final.recomendacao}
        sub={`Por fora compensa ${final.equilibrio_texto}`}
        numeroRotulo="Diferença por ano"
        numero={brl(Math.abs(final.diferenca))}
        numeroSub="na receita líquida de tributos"
        acoes={acoes}
      />
      <Indicadores
        itens={[
          { rotulo: "Vendas a empresas (B2B)", valor: pct(r.percentual_b2b, 0) },
          { rotulo: "Crédito ao cliente a cada R$ 100 — no DAS", valor: brl(final.credito_cliente_dentro) },
          { rotulo: "Crédito ao cliente a cada R$ 100 — por fora", valor: brl(final.credito_cliente_fora) },
        ]}
      />
      <Cartao titulo="Comparativo por ano">
        <div className="overflow-x-auto">
          <table className="num w-full min-w-[640px] text-sm">
            <thead>
              <tr className="border-b border-borda text-xs text-tinta-2">
                <th className="py-2 pr-2 text-left font-medium">Ano</th>
                <th className={th}>Receita líquida — no DAS</th>
                <th className={th}>Receita líquida — por fora</th>
                <th className={th}>Diferença</th>
                <th className="px-2 py-2 text-left font-medium">Por fora compensa</th>
              </tr>
            </thead>
            <tbody>
              {r.cenarios.map((c) => (
                <tr key={c.ano} className="border-b border-borda/70">
                  <td className="py-1.5 pr-2">{c.ano}</td>
                  <td className={`${td} ${c.diferenca <= 0 ? "font-semibold" : ""}`}>{brl(c.dentro_do_das)}</td>
                  <td className={`${td} ${c.diferenca > 0 ? "font-semibold" : ""}`}>{brl(c.por_fora)}</td>
                  <td className={td}>{brl(c.diferenca)}</td>
                  <td className="px-2 py-1.5">{c.equilibrio_texto}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Cartao>
      <Cartao
        titulo="Quanto as vendas a empresas pesam na decisão"
        acoes={
          <div className="flex gap-1" role="group" aria-label="Ano da curva">
            {anos.map((a) => (
              <button
                key={a}
                onClick={() => setAnoCurva(a)}
                aria-pressed={anoCurva === a}
                className={`h-8 rounded-lg px-3 text-xs font-medium ${anoCurva === a ? "bg-marca text-white" : "text-tinta-2 hover:bg-fundo"}`}
              >
                {a}
              </button>
            ))}
          </div>
        }
      >
        <GraficoCurvaB2B pontos={r.curvas[anoCurva]} atual={{ b2b: r.percentual_b2b, diferenca: cenarioCurva.diferenca }} />
        <p className="text-xs text-tinta-2">
          Acima da linha tracejada, recolher IBS/CBS por fora rende mais; abaixo, manter no DAS. O ponto marca a situação atual.
        </p>
      </Cartao>
      <ListaAlertas alertas={r.cenarios.flatMap((c) => c.alertas)} />
      <MemoriaCalculo blocos={r.cenarios.map((c) => ({ titulo: String(c.ano), total: brl(c.diferenca), passos: c.memoria }))} />
    </div>
  );
}

export function ResultadoAutonomo({ r, acoes }: { r: TResultadoAutonomo; acoes?: ReactNode }) {
  const aplicaveis = r.opcoes.filter((o) => o.aplicavel);
  const melhor = aplicaveis.find((o) => o.nome === r.melhor);
  return (
    <div className="flex flex-col gap-4">
      <Destaque
        rotulo="Opção mais vantajosa"
        titulo={r.melhor}
        sub={melhor ? `Sobram ${brl(melhor.liquido_mensal)} por mês${melhor.detalhe ? ` · ${melhor.detalhe}` : ""}` : undefined}
        numeroRotulo={r.ganho_vs_autonomo_anual > 0 ? "Ganho frente ao autônomo" : undefined}
        numero={r.ganho_vs_autonomo_anual > 0 ? brl(r.ganho_vs_autonomo_anual) : undefined}
        numeroSub="por ano"
        acoes={acoes}
      />
      <Cartao titulo="Quanto sobra por mês">
        <GraficoBarras
          descricao={`Valor líquido mensal por opção; melhor: ${r.melhor}`}
          itens={aplicaveis.map((o) => ({
            rotulo: o.nome,
            valor: o.liquido_mensal,
            destaque: o.nome === r.melhor,
            detalhe: `Tributos ${brl(o.tributos_mensais)} · contabilidade ${brl(o.custos_mensais)}`,
          }))}
          naoAplicaveis={r.opcoes.filter((o) => !o.aplicavel).map((o) => o.nome)}
        />
        <div className="mt-4 overflow-x-auto">
          <table className="num w-full min-w-[600px] text-sm">
            <thead>
              <tr className="border-b border-borda text-xs text-tinta-2">
                <th className="py-2 pr-2 text-left font-medium">Opção</th>
                <th className={th}>Tributos/mês</th>
                <th className={th}>Contabilidade/mês</th>
                <th className={th}>Sobra no mês</th>
                <th className="px-2 py-2 text-left font-medium">Observação</th>
              </tr>
            </thead>
            <tbody>
              {aplicaveis.map((o) => (
                <tr key={o.nome} className={`border-b border-borda/70 ${o.nome === r.melhor ? "bg-fundo font-semibold" : ""}`}>
                  <td className="py-1.5 pr-2">{o.nome}</td>
                  <td className={td}>{brl(o.tributos_mensais)}</td>
                  <td className={td}>{brl(o.custos_mensais)}</td>
                  <td className={td}>{brl(o.liquido_mensal)}</td>
                  <td className="px-2 py-1.5 text-xs font-normal text-tinta-2">{o.detalhe || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Cartao>
      <ListaAlertas alertas={[...r.alertas, ...r.opcoes.flatMap((o) => o.alertas)]} />
      <MemoriaCalculo blocos={aplicaveis.map((o) => ({ titulo: o.nome, total: `${brl(o.tributos_mensais)}/mês`, passos: o.memoria }))} />
    </div>
  );
}

export function ResultadoProLabore({ r, acoes }: { r: TResultadoProLabore; acoes?: ReactNode }) {
  const curtos = ["100% pró-labore", "Pró-labore + dividendos"];
  const maisBarato = r.cenarios[0].custo_mensal <= r.cenarios[1].custo_mensal ? 0 : 1;
  return (
    <div className="flex flex-col gap-4">
      <Destaque
        rotulo="Estratégia recomendada"
        titulo={r.melhor}
        numeroRotulo="Economia por ano"
        numero={brl(Math.abs(r.economia_anual))}
        numeroSub={`${brl(Math.abs(r.economia_mensal))} por mês`}
        acoes={acoes}
      />
      <Cartao titulo="Custo tributário mensal da retirada">
        <GraficoBarras
          descricao="Custo tributário mensal por estratégia de retirada"
          itens={r.cenarios.map((c, i) => ({ rotulo: curtos[i], valor: c.custo_mensal, destaque: i === maisBarato, detalhe: c.descricao }))}
        />
        <div className="mt-4 overflow-x-auto">
          <table className="num w-full min-w-[600px] text-sm">
            <thead>
              <tr className="border-b border-borda text-xs text-tinta-2">
                <th className="py-2 pr-2 text-left font-medium">Cenário</th>
                <th className={th}>Pró-labore</th>
                <th className={th}>Dividendos</th>
                <th className={th}>Custo tributário/mês</th>
                <th className={th}>Líquido ao sócio/mês</th>
              </tr>
            </thead>
            <tbody>
              {r.cenarios.map((c, i) => (
                <tr key={c.descricao} className={`border-b border-borda/70 ${i === maisBarato ? "bg-fundo font-semibold" : ""}`}>
                  <td className="py-1.5 pr-2">{c.descricao}</td>
                  <td className={td}>{brl(c.pro_labore)}</td>
                  <td className={td}>{brl(c.dividendos)}</td>
                  <td className={td}>{brl(c.custo_mensal)}</td>
                  <td className={td}>{brl(c.liquido_mensal)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Cartao>
      <ListaAlertas alertas={r.cenarios.flatMap((c) => c.alertas)} />
      <MemoriaCalculo blocos={r.cenarios.map((c) => ({ titulo: c.descricao, total: `${brl(c.custo_mensal)}/mês`, passos: c.memoria }))} />
    </div>
  );
}

export function ResultadoSalario({ r }: { r: TResultadoSalario }) {
  return (
    <div className="flex flex-col gap-4">
      <Destaque
        rotulo="Salário líquido"
        titulo={brl(r.liquido)}
        sub={`Bruto de ${brl(r.salario_bruto)}`}
        numeroRotulo="Descontos"
        numero={brl(r.salario_bruto - r.liquido)}
        numeroSub={pct((r.salario_bruto - r.liquido) / r.salario_bruto) + " do bruto"}
      />
      <Indicadores itens={r.tributos.map((t) => ({ rotulo: t.nome, valor: brl(t.valor) }))} />
      <MemoriaCalculo blocos={[{ titulo: "Holerite", total: brl(r.liquido), passos: r.memoria }]} />
    </div>
  );
}
