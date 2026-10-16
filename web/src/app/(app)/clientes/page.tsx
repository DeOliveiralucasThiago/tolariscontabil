"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { CompletarCadastros } from "@/components/CompletarCadastros";
import { BotaoLink, Cartao, Etiqueta, MensagemErro, Titulo, classeCampo } from "@/components/ui";
import { api, ErroApi } from "@/lib/api";
import { data, mascaraCnpj } from "@/lib/formato";
import { ROTULO_ATIVIDADE, ROTULO_STATUS, type Cliente, type StatusCliente } from "@/lib/tipos";

export default function Clientes() {
  const [clientes, setClientes] = useState<Cliente[] | null>(null);
  const [busca, setBusca] = useState("");
  const [status, setStatus] = useState<StatusCliente | "">("");
  const [erro, setErro] = useState("");
  const [versao, setVersao] = useState(0);

  useEffect(() => {
    const params = new URLSearchParams();
    if (busca.trim()) params.set("busca", busca.trim());
    if (status) params.set("status", status);
    const t = setTimeout(() => {
      api<Cliente[]>(`/clientes?${params}`)
        .then(setClientes)
        .catch((e) => setErro(e instanceof ErroApi ? e.message : "Falha ao carregar"));
    }, 250);
    return () => clearTimeout(t);
  }, [busca, status, versao]);

  return (
    <>
      <Titulo sub="Clientes e prospects do escritório." acoes={
        <div className="flex gap-2">
          <BotaoLink href="/clientes/importar" variante="secundario">Importar planilha</BotaoLink>
          <BotaoLink href="/clientes/novo">Novo cliente</BotaoLink>
        </div>
      }>
        Clientes
      </Titulo>
      <Cartao>
        <CompletarCadastros onProgresso={() => setVersao((v) => v + 1)} />
        <div className="mb-4 flex flex-wrap gap-3">
          <input
            aria-label="Buscar por nome ou CNPJ"
            placeholder="Buscar por nome ou CNPJ…"
            className={`${classeCampo} max-w-sm`}
            value={busca}
            onChange={(e) => setBusca(e.target.value)}
          />
          <div className="flex gap-1" role="group" aria-label="Filtrar por situação">
            {(["", "prospect", "ativo", "inativo"] as const).map((s) => (
              <button
                key={s || "todos"}
                onClick={() => setStatus(s)}
                aria-pressed={status === s}
                className={`h-10 rounded-lg px-3 text-sm font-medium ${status === s ? "bg-marca text-white" : "text-tinta-2 hover:bg-fundo"}`}
              >
                {s ? ROTULO_STATUS[s] : "Todos"}
              </button>
            ))}
          </div>
        </div>
        <MensagemErro>{erro}</MensagemErro>
        {clientes && clientes.length === 0 && (
          <div className="py-10 text-center text-sm text-tinta-2">
            Nenhum cliente encontrado.{" "}
            <Link href="/prospeccao" className="font-medium text-marca hover:underline">Comece por uma prospecção</Link>.
          </div>
        )}
        {clientes && clientes.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[640px] text-sm">
              <thead>
                <tr className="border-b border-borda text-left text-xs text-tinta-2">
                  <th className="py-2 font-medium">Empresa</th>
                  <th className="py-2 font-medium">CNPJ</th>
                  <th className="py-2 font-medium">Atividade</th>
                  <th className="py-2 font-medium">Situação</th>
                  <th className="py-2 text-right font-medium">Simulações</th>
                  <th className="py-2 text-right font-medium">Última</th>
                </tr>
              </thead>
              <tbody>
                {clientes.map((c) => (
                  <tr key={c.id} className="border-b border-borda/70 hover:bg-fundo">
                    <td className="py-2.5">
                      <Link href={`/clientes/${c.id}`} className="font-medium hover:text-marca">{c.razao_social}</Link>
                      {c.nome_fantasia && <div className="text-xs text-tinta-2">{c.nome_fantasia}</div>}
                      {c.cadastro_pendente && <div className="text-xs text-amber-800">Cadastro por completar</div>}
                    </td>
                    <td className="num py-2.5 text-tinta-2">{c.cnpj ? mascaraCnpj(c.cnpj) : "—"}</td>
                    <td className="py-2.5">{c.atividade ? ROTULO_ATIVIDADE[c.atividade] : "—"}</td>
                    <td className="py-2.5"><Etiqueta tom={c.status}>{ROTULO_STATUS[c.status]}</Etiqueta></td>
                    <td className="num py-2.5 text-right">{c.total_simulacoes}</td>
                    <td className="num py-2.5 text-right text-tinta-2">{data(c.ultima_simulacao_em)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Cartao>
    </>
  );
}
