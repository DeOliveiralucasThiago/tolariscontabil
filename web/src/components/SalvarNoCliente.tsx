"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { api, ErroApi, urlProposta } from "@/lib/api";
import type { Cliente, Simulacao } from "@/lib/tipos";

import { Botao, MensagemErro, classeCampo } from "./ui";

/** Salva a simulação no histórico de um cliente e libera o relatório em PDF. */
export function SalvarNoCliente({
  rota,
  entrada,
  clienteInicial,
}: {
  rota: string;
  entrada: unknown;
  clienteInicial?: number;
}) {
  const [clientes, setClientes] = useState<Cliente[]>([]);
  const [clienteId, setClienteId] = useState<number | "">(clienteInicial ?? "");
  const [salvo, setSalvo] = useState<Simulacao | null>(null);
  const [erro, setErro] = useState("");
  const [salvando, setSalvando] = useState(false);

  useEffect(() => {
    api<Cliente[]>("/clientes").then(setClientes).catch(() => setClientes([]));
  }, []);

  // Nova entrada = novo cálculo: o salvamento anterior não vale mais
  useEffect(() => setSalvo(null), [entrada]);

  async function salvar() {
    if (!clienteId) return setErro("Escolha o cliente.");
    setErro("");
    setSalvando(true);
    try {
      setSalvo(await api<Simulacao>(`/clientes/${clienteId}/simulacoes/${rota}`, { method: "POST", json: entrada }));
    } catch (e) {
      setErro(e instanceof ErroApi ? e.message : "Falha ao salvar");
    } finally {
      setSalvando(false);
    }
  }

  if (salvo) {
    return (
      <div className="flex flex-wrap gap-2">
        <a href={urlProposta(salvo.id)} target="_blank" className="inline-flex h-10 items-center rounded-lg bg-marca px-4 text-sm font-medium text-white">
          Abrir relatório em PDF
        </a>
        <Link href={`/clientes/${salvo.cliente_id}`} className="inline-flex h-10 items-center rounded-lg border border-borda px-4 text-sm font-medium">
          Ver cliente
        </Link>
      </div>
    );
  }

  return (
    <div className="flex w-full flex-col gap-2">
      <div className="flex flex-wrap gap-2">
        <select
          aria-label="Cliente"
          className={`${classeCampo} max-w-xs`}
          value={clienteId}
          onChange={(e) => setClienteId(e.target.value ? Number(e.target.value) : "")}
        >
          <option value="">Salvar no cliente…</option>
          {clientes.map((c) => (
            <option key={c.id} value={c.id}>{c.razao_social}</option>
          ))}
        </select>
        <Botao onClick={salvar} carregando={salvando} disabled={!clienteId}>
          Salvar e gerar PDF
        </Botao>
      </div>
      {clientes.length === 0 && (
        <p className="text-xs text-tinta-2">
          Nenhum cliente cadastrado. <Link href="/clientes/novo" className="text-marca hover:underline">Cadastre um cliente</Link> para salvar.
        </p>
      )}
      <MensagemErro>{erro}</MensagemErro>
    </div>
  );
}
