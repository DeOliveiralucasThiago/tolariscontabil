"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { ChipGravidade } from "@/components/Gravidade";
import { Abas, Botao, Cartao, MensagemErro, Titulo } from "@/components/ui";
import { api, ErroApi } from "@/lib/api";
import { brl } from "@/lib/formato";
import type { AvisoCarteira, Gravidade, MudancaLegal, RespostaAvisos, Simulacao } from "@/lib/tipos";

type Filtro = "todos" | Gravidade;

const dataBr = (iso: string) => new Date(`${iso}T12:00:00`).toLocaleDateString("pt-BR");

function CartaoAviso({ a, onRecalcular, ocupado }: { a: AvisoCarteira; onRecalcular: (a: AvisoCarteira) => void; ocupado: boolean }) {
  return (
    <li className="rounded-xl border border-borda bg-superficie p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <ChipGravidade gravidade={a.gravidade} />
            <Link href={`/clientes/${a.cliente_id}`} className="text-sm font-medium text-tinta-2 hover:text-marca">
              {a.cliente}
            </Link>
          </div>
          <h3 className="mt-2 text-[15px] font-semibold">{a.titulo}</h3>
          <p className="mt-1 text-sm text-tinta-2">{a.detalhe}</p>
          {a.base_legal && <p className="mt-1 text-xs text-tinta-2">Base legal: {a.base_legal}</p>}
        </div>
        <div className="flex flex-col items-end gap-2">
          {a.valor != null && a.valor > 0 && (
            <div className="text-right">
              <div className="num text-lg font-semibold">{brl(a.valor)}</div>
              <div className="text-xs text-tinta-2">{a.gravidade === "oportunidade" ? "a ganhar" : "em jogo"}</div>
            </div>
          )}
          {a.acao.tipo === "recalcular" ? (
            <Botao variante="secundario" onClick={() => onRecalcular(a)} carregando={ocupado}>
              {a.acao.rotulo}
            </Botao>
          ) : (
            <Link
              href={`/clientes/${a.cliente_id}${a.acao.aba ? `?aba=${a.acao.aba}` : ""}`}
              className="inline-flex h-10 items-center rounded-lg border border-borda px-3 text-sm font-medium hover:bg-fundo"
            >
              {a.acao.rotulo}
            </Link>
          )}
        </div>
      </div>
    </li>
  );
}

function Mudancas({ itens }: { itens: MudancaLegal[] }) {
  return (
    <Cartao titulo="Mudanças na legislação">
      <p className="mb-3 text-sm text-tinta-2">
        O que já está incorporado aos cálculos do Tolaris, das próximas vigências para as que já valem. Quando uma regra mudar,
        as simulações afetadas aparecem acima, prontas para recalcular.
      </p>
      <ul className="flex flex-col gap-2">
        {itens.map((m) => (
          <li key={m.id}>
            <details className="group rounded-lg border border-borda">
              <summary className="flex cursor-pointer list-none flex-wrap items-start gap-x-3 gap-y-1.5 px-4 py-3 text-sm">
                <span
                  className={`mt-0.5 shrink-0 rounded-full border px-2 py-0.5 text-xs font-medium ${
                    m.vigente ? "border-emerald-200 bg-emerald-50 text-emerald-800" : "border-sky-200 bg-sky-50 text-sky-800"
                  }`}
                >
                  {m.vigente ? "Em vigor" : "Futura"} · {dataBr(m.data)}
                </span>
                <span className="min-w-[13rem] flex-1 font-medium">{m.titulo}</span>
                <span aria-hidden className="inline-block transition group-open:rotate-90">›</span>
              </summary>
              <div className="flex flex-col gap-2 border-t border-borda px-4 py-3 text-sm">
                <p>{m.resumo}</p>
                <p className="text-tinta-2">
                  <strong className="font-medium text-tinta">Para o escritório:</strong> {m.efeito}
                </p>
                {m.observacao && <p className="text-xs text-amber-800">⚠ {m.observacao}</p>}
                <p className="text-xs text-tinta-2">Base legal: {m.base_legal}</p>
              </div>
            </details>
          </li>
        ))}
      </ul>
    </Cartao>
  );
}

export default function PaginaAvisos() {
  const [dados, setDados] = useState<RespostaAvisos | null>(null);
  const [mudancas, setMudancas] = useState<MudancaLegal[]>([]);
  const [filtro, setFiltro] = useState<Filtro>("todos");
  const [ocupado, setOcupado] = useState<number | null>(null);
  const [feito, setFeito] = useState<{ cliente: string; clienteId: number } | null>(null);
  const [erro, setErro] = useState("");

  const carregar = useCallback(async () => {
    try {
      setDados(await api<RespostaAvisos>("/avisos"));
    } catch (e) {
      setErro(e instanceof ErroApi ? e.message : "Falha ao carregar os avisos");
    }
  }, []);

  useEffect(() => {
    carregar();
    api<MudancaLegal[]>("/mudancas").then(setMudancas).catch(() => setMudancas([]));
  }, [carregar]);

  async function recalcular(a: AvisoCarteira) {
    if (a.acao.simulacao_id == null) return;
    setErro("");
    setFeito(null);
    setOcupado(a.acao.simulacao_id);
    try {
      await api<Simulacao>(`/simulacoes/${a.acao.simulacao_id}/recalcular`, { method: "POST" });
      setFeito({ cliente: a.cliente, clienteId: a.cliente_id });
      await carregar();
    } catch (e) {
      setErro(e instanceof ErroApi ? e.message : "Não foi possível recalcular");
    } finally {
      setOcupado(null);
    }
  }

  const r = dados?.resumo;
  const abas: { id: Filtro; rotulo: string }[] = [
    { id: "todos", rotulo: `Todos (${r?.total ?? 0})` },
    { id: "critico", rotulo: `Críticos (${r?.critico ?? 0})` },
    { id: "atencao", rotulo: `Atenção (${r?.atencao ?? 0})` },
    { id: "oportunidade", rotulo: `Oportunidades (${r?.oportunidade ?? 0})` },
    { id: "info", rotulo: `Informações (${r?.info ?? 0})` },
  ];
  const visiveis = (dados?.avisos ?? []).filter((a) => filtro === "todos" || a.gravidade === filtro);

  return (
    <>
      <Titulo sub={dados ? `${dados.clientes_analisados} clientes analisados` : "Analisando a carteira…"}>Avisos</Titulo>
      <MensagemErro>{erro}</MensagemErro>
      {feito && (
        <div role="status" className="mb-4 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-900">
          Simulação de {feito.cliente} recalculada com as regras atuais.{" "}
          <Link href={`/clientes/${feito.clienteId}`} className="font-medium underline">
            Ver no cliente
          </Link>
          . A versão anterior continua no histórico.
        </div>
      )}
      {dados && r && (
        <div className="flex flex-col gap-6">
          {r.oportunidade > 0 && (
            <div className="rounded-xl border-2 border-marca bg-superficie p-5">
              <div className="text-xs font-medium uppercase tracking-wide text-tinta-2">Oportunidades identificadas</div>
              <div className="num mt-1 text-3xl font-semibold text-marca">{brl(r.valor_oportunidades)}</div>
              <div className="text-sm text-tinta-2">em {r.oportunidade} {r.oportunidade === 1 ? "oportunidade" : "oportunidades"} na carteira</div>
            </div>
          )}
          <div>
            <Abas abas={abas} ativa={filtro} onChange={setFiltro} />
            {visiveis.length === 0 ? (
              <Cartao>
                <div className="py-6 text-center text-sm text-tinta-2">
                  {r.total === 0
                    ? "Nenhum aviso agora. O Tolaris acompanha fator R, limites do MEI, do Simples e do Presumido, produtos monofásicos e simulações que deixaram de valer por mudança de regra."
                    : "Nenhum aviso neste filtro."}
                </div>
              </Cartao>
            ) : (
              <ul className="flex flex-col gap-3">
                {visiveis.map((a) => (
                  <CartaoAviso key={a.id} a={a} onRecalcular={recalcular} ocupado={ocupado === a.acao.simulacao_id} />
                ))}
              </ul>
            )}
          </div>
          {mudancas.length > 0 && <Mudancas itens={mudancas} />}
        </div>
      )}
    </>
  );
}
