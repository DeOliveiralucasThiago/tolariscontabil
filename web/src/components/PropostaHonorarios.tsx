"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { api, ErroApi } from "@/lib/api";
import { brl, dataHora } from "@/lib/formato";
import type { Simulacao, SugestaoHonorarios } from "@/lib/tipos";

import { CampoMoeda } from "./CampoMoeda";
import { Botao, Campo, MensagemErro, Rotulo, classeCampo } from "./ui";

const NOME_REGIME: Record<string, string> = { mei: "MEI", simples: "Simples Nacional", presumido: "Lucro Presumido", real: "Lucro Real" };

/** Proposta de honorários de uma simulação: sugestão pela tabela do escritório, ajuste e gravação. */
export function PropostaHonorarios({
  sim,
  onAtualizada,
  onFechar,
}: {
  sim: Simulacao;
  onAtualizada: (sim: Simulacao) => void;
  onFechar: () => void;
}) {
  const h = sim.honorarios ?? null;
  const aceita = Boolean(sim.aceite_em);
  const [funcionarios, setFuncionarios] = useState(h?.funcionarios ?? 0);
  const [valor, setValor] = useState(h?.valor_mensal ?? 0);
  const [adesao, setAdesao] = useState(h?.adesao ?? 0);
  const [servicos, setServicos] = useState(h?.servicos ?? "");
  const [validade, setValidade] = useState(h?.validade_dias ?? 15);
  const [sugestao, setSugestao] = useState<SugestaoHonorarios | null>(null);
  const [erro, setErro] = useState("");
  const [ok, setOk] = useState("");
  const [salvando, setSalvando] = useState(false);
  const iniciado = useRef(false);
  const editouValor = useRef(Boolean(h));

  useEffect(() => {
    let atual = true;
    api<SugestaoHonorarios>(`/simulacoes/${sim.id}/honorarios/sugestao?funcionarios=${funcionarios}`)
      .then((s) => {
        if (!atual) return;
        setSugestao(s);
        if (!iniciado.current && !h) {
          setAdesao(s.adesao);
          setServicos(s.servicos);
          setValidade(s.validade_dias);
        }
        iniciado.current = true;
        if (!editouValor.current) setValor(s.valor_mensal);
      })
      .catch(() => atual && setSugestao(null));
    return () => {
      atual = false;
    };
  }, [sim.id, funcionarios, h]);

  const totalAno = valor * 12 + adesao;
  const economia = sim.resultado.economia_vs_pior ?? 0;
  const razao = totalAno > 0 && economia > 0 ? economia / totalAno : 0;

  async function salvar(e: React.FormEvent) {
    e.preventDefault();
    setErro("");
    setOk("");
    setSalvando(true);
    try {
      const nova = await api<Simulacao>(`/simulacoes/${sim.id}/honorarios`, {
        method: "PUT",
        json: { funcionarios, valor_mensal: valor, adesao, servicos, validade_dias: validade },
      });
      onAtualizada(nova);
      setOk("Proposta salva. Ela já aparece no PDF; para o cliente aceitar pelo portal, marque o relatório como “No portal”.");
    } catch (e) {
      setErro(e instanceof ErroApi ? e.message : "Não foi possível salvar a proposta");
    } finally {
      setSalvando(false);
    }
  }

  async function remover() {
    if (!confirm("Remover a proposta de honorários desta simulação?")) return;
    setErro("");
    try {
      await api(`/simulacoes/${sim.id}/honorarios`, { method: "DELETE" });
      onAtualizada({ ...sim, honorarios: null });
      onFechar();
    } catch (e) {
      setErro(e instanceof ErroApi ? e.message : "Não foi possível remover");
    }
  }

  return (
    <form onSubmit={salvar} className="mt-3 flex flex-col gap-4 rounded-lg border border-borda bg-fundo p-4" aria-label="Proposta de honorários">
      <div className="text-sm font-medium">Proposta de honorários</div>
      {aceita && (
        <div role="status" className="rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-900">
          Aceita por <strong>{sim.aceite_nome}</strong> em {dataHora(sim.aceite_em)}. Uma proposta aceita não pode mais ser alterada.
        </div>
      )}
      <fieldset disabled={aceita} className="flex flex-col gap-4 disabled:opacity-70">
        <div className="grid gap-4 sm:grid-cols-4">
          <Campo
            rotulo="Funcionários (CLT)"
            name={`hon-func-${sim.id}`}
            type="number"
            min={0}
            max={10000}
            value={funcionarios}
            onChange={(e) => setFuncionarios(Math.max(0, Number(e.target.value) || 0))}
          />
          <CampoMoeda
            id={`hon-valor-${sim.id}`}
            rotulo="Honorário mensal"
            valor={valor}
            onChange={(v) => {
              editouValor.current = true;
              setValor(v);
            }}
          />
          <CampoMoeda id={`hon-adesao-${sim.id}`} rotulo="Adesão (único)" valor={adesao} onChange={setAdesao} />
          <Campo
            rotulo="Validade (dias)"
            name={`hon-validade-${sim.id}`}
            type="number"
            min={1}
            max={90}
            value={validade}
            onChange={(e) => setValidade(Math.min(90, Math.max(1, Number(e.target.value) || 1)))}
          />
        </div>
        <div>
          <Rotulo htmlFor={`hon-servicos-${sim.id}`}>Serviços incluídos (um por linha)</Rotulo>
          <textarea
            id={`hon-servicos-${sim.id}`}
            rows={3}
            maxLength={2000}
            className={`${classeCampo} h-auto py-2`}
            value={servicos}
            onChange={(e) => setServicos(e.target.value)}
          />
        </div>
      </fieldset>
      <div className="text-xs text-tinta-2">
        {sugestao && sugestao.configurado && sugestao.regime ? (
          <>
            Sugestão pela tabela: {NOME_REGIME[sugestao.regime]} {brl(sugestao.base)}
            {sugestao.por_funcionario > 0 && <> + {funcionarios} × {brl(sugestao.por_funcionario)}</>} = {brl(sugestao.valor_mensal)} por mês.
          </>
        ) : (
          <>
            Sem valor sugerido: o regime recomendado não consta na tabela.{" "}
            <Link href="/configuracoes" className="font-medium text-marca hover:underline">
              Preencha a tabela de honorários
            </Link>
            .
          </>
        )}
      </div>
      {valor > 0 && (
        <div className="num rounded-lg border border-borda bg-superficie px-3 py-2 text-sm">
          Total no primeiro ano: <strong>{brl(totalAno)}</strong>
          {economia > 0 && (
            <>
              {" "}
              · economia estimada de {brl(economia)} por ano
              {razao >= 1 && <> (cerca de {razao.toFixed(1).replace(".", ",")} vezes os honorários)</>}
            </>
          )}
        </div>
      )}
      <MensagemErro>{erro}</MensagemErro>
      {ok && <p className="text-sm text-emerald-700">{ok}</p>}
      <div className="flex flex-wrap gap-2">
        {!aceita && (
          <Botao type="submit" carregando={salvando} disabled={valor <= 0}>
            {h ? "Atualizar proposta" : "Salvar proposta"}
          </Botao>
        )}
        {h && !aceita && (
          <Botao type="button" variante="perigo" onClick={remover}>
            Remover proposta
          </Botao>
        )}
        <Botao type="button" variante="fantasma" onClick={onFechar}>
          Fechar
        </Botao>
      </div>
    </form>
  );
}
