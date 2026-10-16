"use client";

import { useState } from "react";

import { api, ErroApi } from "@/lib/api";
import { brl, dataHora } from "@/lib/formato";

import { Botao, Campo, MensagemErro } from "./ui";

export interface HonorariosPublico {
  valor_mensal: number;
  adesao: number;
  servicos: string;
  valido_ate: string;
  expirada: boolean;
}

const dataBr = (iso: string) => new Date(`${iso}T12:00:00`).toLocaleDateString("pt-BR");

/** Proposta de honorários vista pelo cliente no portal, com o aceite eletrônico. */
export function PropostaNoPortal({
  token,
  simulacaoId,
  cliente,
  honorarios: h,
  aceiteEm,
  aceiteNome,
  onAceita,
}: {
  token: string;
  simulacaoId: number;
  cliente: string;
  honorarios: HonorariosPublico;
  aceiteEm: string | null;
  aceiteNome: string | null;
  onAceita: () => void;
}) {
  const [nome, setNome] = useState("");
  const [confirmo, setConfirmo] = useState(false);
  const [erro, setErro] = useState("");
  const [enviando, setEnviando] = useState(false);
  const linhas = h.servicos.split("\n").map((x) => x.trim()).filter(Boolean);

  async function aceitar(e: React.FormEvent) {
    e.preventDefault();
    setErro("");
    setEnviando(true);
    try {
      await api(`/portal/${encodeURIComponent(token)}/simulacoes/${simulacaoId}/aceite`, { method: "POST", json: { nome, confirmo } });
      onAceita();
    } catch (e) {
      setErro(e instanceof ErroApi ? e.message : "Não foi possível registrar o aceite");
    } finally {
      setEnviando(false);
    }
  }

  return (
    <section aria-label="Proposta de honorários" className="rounded-xl border-2 border-marca bg-superficie p-5">
      <h2 className="text-base font-semibold">Proposta de honorários</h2>
      <div className="mt-3 grid gap-3 sm:grid-cols-3">
        <div className="rounded-lg border border-borda px-4 py-3">
          <div className="text-xs text-tinta-2">Honorários mensais</div>
          <div className="num text-lg font-semibold">{brl(h.valor_mensal)}</div>
        </div>
        {h.adesao > 0 && (
          <div className="rounded-lg border border-borda px-4 py-3">
            <div className="text-xs text-tinta-2">Adesão (pagamento único)</div>
            <div className="num text-lg font-semibold">{brl(h.adesao)}</div>
          </div>
        )}
        <div className="rounded-lg border border-borda px-4 py-3">
          <div className="text-xs text-tinta-2">Total no primeiro ano</div>
          <div className="num text-lg font-semibold">{brl(h.valor_mensal * 12 + h.adesao)}</div>
        </div>
      </div>
      {linhas.length > 0 && (
        <div className="mt-4 text-sm">
          <div className="font-medium">Serviços incluídos</div>
          <ul className="mt-1 list-disc pl-5 text-tinta-2">
            {linhas.map((l) => (
              <li key={l}>{l}</li>
            ))}
          </ul>
        </div>
      )}
      {aceiteEm ? (
        <p role="status" className="mt-4 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-900">
          ✓ Proposta aceita por <strong>{aceiteNome}</strong> em {dataHora(aceiteEm)}. O escritório entrará em contato para formalizar.
        </p>
      ) : h.expirada ? (
        <p className="mt-4 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">
          Esta proposta venceu em {dataBr(h.valido_ate)}. Peça uma nova ao seu escritório.
        </p>
      ) : (
        <form onSubmit={aceitar} className="mt-4 flex flex-col gap-3 border-t border-borda pt-4">
          <p className="text-sm text-tinta-2">Proposta válida até {dataBr(h.valido_ate)}.</p>
          <Campo
            rotulo="Seu nome completo"
            name="aceite-nome"
            required
            minLength={3}
            maxLength={200}
            autoComplete="name"
            value={nome}
            onChange={(e) => setNome(e.target.value)}
            className="sm:max-w-md"
          />
          <label className="flex items-start gap-2 text-sm">
            <input type="checkbox" checked={confirmo} onChange={(e) => setConfirmo(e.target.checked)} className="mt-1 accent-[var(--marca)]" />
            <span>Li a proposta e aceito os honorários acima em nome de {cliente}.</span>
          </label>
          <MensagemErro>{erro}</MensagemErro>
          <div>
            <Botao type="submit" carregando={enviando} disabled={!confirmo || nome.trim().length < 3}>
              Aceitar proposta
            </Botao>
          </div>
          <p className="text-xs text-tinta-2">Registramos seu nome, a data, a hora e o endereço IP como comprovante do aceite.</p>
        </form>
      )}
    </section>
  );
}
