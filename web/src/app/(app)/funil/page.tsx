"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { Indicadores } from "@/components/Blocos";
import { Abas, Cartao, Etiqueta, MensagemErro, Selecao, Titulo } from "@/components/ui";
import { api, ErroApi } from "@/lib/api";
import { brl, data, pct } from "@/lib/formato";
import type { EtapaFunil, Funil, PropostaFunil } from "@/lib/tipos";

const COR_BARRA = "#2a78d6";
const dataBr = (iso: string) => new Date(`${iso}T12:00:00`).toLocaleDateString("pt-BR"); // data sem hora: evita voltar um dia pelo fuso
type Filtro = "todas" | "acao" | "abertas" | "aceitas" | "vencidas";
const PERIODOS = [
  { valor: 30, rotulo: "Últimos 30 dias" },
  { valor: 90, rotulo: "Últimos 90 dias" },
  { valor: 365, rotulo: "Últimos 12 meses" },
  { valor: 0, rotulo: "Todas" },
];
const TOM_ETAPA: Record<PropostaFunil["etapa"], string> = { criada: "inativo", enviada: "prospect", vista: "prospect", aceita: "ativo", vencida: "inativo" };

/** "no mesmo dia" ou "em 3,5 dias" */
const prazo = (dias: number) => (dias < 0.5 ? "no mesmo dia" : `em ${dias.toLocaleString("pt-BR")} ${dias === 1 ? "dia" : "dias"}`);

function Barras({ etapas }: { etapas: EtapaFunil[] }) {
  const maior = Math.max(1, ...etapas.map((e) => e.quantidade));
  return (
    <ol className="flex flex-col gap-3" aria-label="Funil de propostas">
      {etapas.map((e) => (
        <li key={e.etapa} className="grid items-center gap-x-4 gap-y-1 sm:grid-cols-[200px_1fr_190px]">
          <div className="text-sm font-medium">{e.rotulo}</div>
          <div className="h-8 rounded bg-fundo" role="img" aria-label={`${e.rotulo}: ${e.quantidade}`}>
            <div className="flex h-full min-w-1 items-center rounded px-2" style={{ width: `${(e.quantidade / maior) * 100}%`, background: COR_BARRA }}>
              <span className="num text-xs font-semibold text-white">{e.quantidade > 0 ? e.quantidade : ""}</span>
            </div>
          </div>
          <div className="text-xs text-tinta-2">
            <span className="num font-medium text-tinta">{brl(e.valor_mensal)}</span> por mês
            {e.conversao != null && <div>{pct(e.conversao, 0)} da etapa anterior</div>}
          </div>
        </li>
      ))}
    </ol>
  );
}

export default function PaginaFunil() {
  const [dias, setDias] = useState(90);
  const [filtro, setFiltro] = useState<Filtro>("todas");
  const [dados, setDados] = useState<Funil | null>(null);
  const [erro, setErro] = useState("");

  useEffect(() => {
    api<Funil>(`/funil?dias=${dias}`)
      .then((r) => {
        setDados(r);
        setErro("");
      })
      .catch((e) => setErro(e instanceof ErroApi ? e.message : "Falha ao carregar o funil"));
  }, [dias]);

  const r = dados?.resumo;
  const lista = (dados?.propostas ?? []).filter((p) =>
    filtro === "todas" ? true
    : filtro === "acao" ? p.acao != null
    : filtro === "abertas" ? ["criada", "enviada", "vista"].includes(p.etapa)
    : filtro === "aceitas" ? p.etapa === "aceita"
    : p.etapa === "vencida",
  );
  const abas: { id: Filtro; rotulo: string }[] = [
    { id: "todas", rotulo: `Todas (${dados?.propostas.length ?? 0})` },
    { id: "acao", rotulo: `Precisam de ação (${dados?.precisam_de_acao ?? 0})` },
    { id: "abertas", rotulo: "Em aberto" },
    { id: "aceitas", rotulo: "Aceitas" },
    { id: "vencidas", rotulo: "Vencidas" },
  ];

  return (
    <>
      <Titulo
        sub="Das propostas de honorários criadas até as aceitas. Conta uma proposta por cliente: a mais recente."
        acoes={
          <Selecao rotulo="Período" name="periodo_funil" value={dias} onChange={(e) => setDias(Number(e.target.value))} className="w-48">
            {PERIODOS.map((p) => <option key={p.valor} value={p.valor}>{p.rotulo}</option>)}
          </Selecao>
        }
      >
        Funil comercial
      </Titulo>
      <div className="flex flex-col gap-4">
        <MensagemErro>{erro}</MensagemErro>
        {r && (
          <Indicadores
            itens={[
              { rotulo: "Honorários aceitos (por mês)", valor: brl(r.aceitas_valor_mensal), detalhe: `${brl(r.aceitas_primeiro_ano)} no primeiro ano, com adesão` },
              { rotulo: "Em aberto (por mês)", valor: brl(r.em_aberto_valor_mensal), detalhe: `${r.em_aberto} ${r.em_aberto === 1 ? "proposta" : "propostas"}${r.vencidas ? ` · ${r.vencidas} vencida${r.vencidas > 1 ? "s" : ""} (${brl(r.vencidas_valor_mensal)}/mês)` : ""}` },
              { rotulo: "Taxa de aceite", valor: r.taxa_aceite == null ? "—" : pct(r.taxa_aceite, 0), detalhe: r.dias_ate_aceite != null ? `Aceitam ${prazo(r.dias_ate_aceite)}, em média` : r.dias_ate_visto != null ? `Abrem ${prazo(r.dias_ate_visto)}, em média` : "das propostas enviadas" },
            ]}
          />
        )}
        {dados && dados.resumo.propostas === 0 ? (
          <Cartao titulo="Nenhuma proposta no período">
            <p className="text-sm text-tinta-2">
              As propostas nascem na aba Simulações de cada cliente (botão Honorários). Defina os valores base em Configurações para o sistema sugerir o
              valor, publique no portal ou envie por e-mail, e acompanhe aqui.
            </p>
          </Cartao>
        ) : (
          dados && (
            <>
              <Cartao titulo="Funil">
                <Barras etapas={dados.funil} />
                <p className="mt-4 text-xs text-tinta-2">
                  Cada etapa conta as propostas que chegaram até ela, mesmo as que depois venceram. “Enviada” é publicar no portal ou mandar por e-mail;
                  “aberta” é o cliente abrir o relatório no portal. Aceite eletrônico simples: formalize o contrato à parte.
                  {r && r.economia_anual_aceitas > 0 && <> Nas simulações dos clientes que aceitaram, o regime recomendado custa {brl(r.economia_anual_aceitas)} por ano a menos que o pior (não é a economia sobre o que pagam hoje).</>}
                </p>
              </Cartao>
              <Cartao titulo="Propostas">
                <Abas abas={abas} ativa={filtro} onChange={setFiltro} />
                {lista.length === 0 ? (
                  <p className="text-sm text-tinta-2">Nenhuma proposta neste filtro.</p>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full min-w-[720px] text-sm">
                      <thead>
                        <tr className="border-b border-borda text-left text-xs text-tinta-2">
                          <th className="py-2 pr-2 font-medium">Cliente</th>
                          <th className="px-2 py-2 font-medium">Etapa</th>
                          <th className="px-2 py-2 text-right font-medium">Por mês</th>
                          <th className="px-2 py-2 text-right font-medium">Adesão</th>
                          <th className="px-2 py-2 font-medium">Válida até</th>
                          <th className="px-2 py-2 font-medium">O que fazer</th>
                        </tr>
                      </thead>
                      <tbody>
                        {lista.map((p) => (
                          <tr key={p.cliente_id} className="border-b border-borda/70 align-top">
                            <td className="py-2 pr-2">
                              <Link href={`/clientes/${p.cliente_id}`} className="font-medium hover:text-marca">{p.cliente}</Link>
                              {p.cliente_status === "prospect" && <div className="text-xs text-tinta-2">Prospect</div>}
                            </td>
                            <td className="px-2 py-2"><Etiqueta tom={TOM_ETAPA[p.etapa]}>{p.rotulo_etapa}</Etiqueta></td>
                            <td className="num px-2 py-2 text-right">{brl(p.valor_mensal)}</td>
                            <td className="num px-2 py-2 text-right text-tinta-2">{p.adesao ? brl(p.adesao) : "—"}</td>
                            <td className="num px-2 py-2 text-tinta-2">{dataBr(p.valido_ate)}</td>
                            <td className="px-2 py-2 text-xs text-tinta-2">{p.acao ?? (p.etapa === "aceita" ? `Aceita em ${data(p.aceite_em)}. Formalize o contrato.` : "No prazo.")}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </Cartao>
            </>
          )
        )}
      </div>
    </>
  );
}
