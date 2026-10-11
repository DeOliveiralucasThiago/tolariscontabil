"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { FormCliente } from "@/components/FormCliente";
import { FormCompleta } from "@/components/FormCompleta";
import { ResultadoComparativo } from "@/components/ResultadoComparativo";
import { Botao, Cartao, Etiqueta, MensagemErro, Titulo } from "@/components/ui";
import { api, ErroApi, urlProposta } from "@/lib/api";
import { brl, dataHora, mascaraCnpj } from "@/lib/formato";
import { ROTULO_ATIVIDADE, ROTULO_REGIME, ROTULO_STATUS, type Cliente, type CompletaEntrada, type Simulacao } from "@/lib/tipos";

type Aba = "simulacoes" | "planejamento" | "dados";

export default function DetalheCliente() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [cliente, setCliente] = useState<Cliente | null>(null);
  const [simulacoes, setSimulacoes] = useState<Simulacao[]>([]);
  const [aberta, setAberta] = useState<Simulacao | null>(null);
  const [aba, setAba] = useState<Aba>("simulacoes");
  const [erro, setErro] = useState("");
  const [calculando, setCalculando] = useState(false);

  const carregar = useCallback(async () => {
    try {
      const [c, s] = await Promise.all([api<Cliente>(`/clientes/${id}`), api<Simulacao[]>(`/clientes/${id}/simulacoes`)]);
      setCliente(c);
      setSimulacoes(s);
    } catch (e) {
      setErro(e instanceof ErroApi ? e.message : "Falha ao carregar");
    }
  }, [id]);

  useEffect(() => {
    carregar();
  }, [carregar]);

  async function calcular(entrada: CompletaEntrada) {
    setErro("");
    setCalculando(true);
    try {
      const sim = await api<Simulacao>(`/clientes/${id}/simulacoes/completa`, { method: "POST", json: entrada });
      setSimulacoes((s) => [sim, ...s]);
      setAberta(sim);
      setAba("simulacoes");
    } catch (e) {
      setErro(e instanceof ErroApi ? e.message : "Falha no cálculo");
    } finally {
      setCalculando(false);
    }
  }

  async function excluirSimulacao(sim: Simulacao) {
    if (!confirm("Excluir esta simulação?")) return;
    await api(`/simulacoes/${sim.id}`, { method: "DELETE" });
    setSimulacoes((s) => s.filter((x) => x.id !== sim.id));
    if (aberta?.id === sim.id) setAberta(null);
  }

  async function excluirCliente() {
    if (!cliente || !confirm(`Excluir ${cliente.razao_social} e todas as simulações? Esta ação não pode ser desfeita.`)) return;
    await api(`/clientes/${cliente.id}`, { method: "DELETE" });
    router.replace("/clientes");
  }

  if (!cliente) {
    return erro ? <MensagemErro>{erro}</MensagemErro> : <p className="text-sm text-tinta-2">Carregando…</p>;
  }

  const abas: { id: Aba; rotulo: string }[] = [
    { id: "simulacoes", rotulo: `Simulações (${simulacoes.length})` },
    { id: "planejamento", rotulo: "Novo planejamento" },
    { id: "dados", rotulo: "Dados cadastrais" },
  ];

  return (
    <>
      <div className="mb-2 text-sm">
        <Link href="/clientes" className="text-tinta-2 hover:text-tinta">← Clientes</Link>
      </div>
      <Titulo
        sub={
          <span className="flex flex-wrap items-center gap-2">
            <Etiqueta tom={cliente.status}>{ROTULO_STATUS[cliente.status]}</Etiqueta>
            {cliente.cnpj && <span className="num">{mascaraCnpj(cliente.cnpj)}</span>}
            {cliente.atividade && <span>· {ROTULO_ATIVIDADE[cliente.atividade]}</span>}
            {cliente.regime_atual && <span>· hoje no {ROTULO_REGIME[cliente.regime_atual]}</span>}
            {cliente.municipio && <span>· {cliente.municipio}/{cliente.uf}</span>}
          </span>
        }
      >
        {cliente.razao_social}
      </Titulo>

      <div className="mb-4 flex gap-1 border-b border-borda" role="tablist">
        {abas.map((a) => (
          <button
            key={a.id}
            role="tab"
            aria-selected={aba === a.id}
            onClick={() => setAba(a.id)}
            className={`-mb-px border-b-2 px-4 py-2 text-sm font-medium ${aba === a.id ? "border-marca text-tinta" : "border-transparent text-tinta-2 hover:text-tinta"}`}
          >
            {a.rotulo}
          </button>
        ))}
      </div>
      <MensagemErro>{erro}</MensagemErro>

      {aba === "simulacoes" && (
        <div className="flex flex-col gap-4">
          {simulacoes.length === 0 ? (
            <Cartao>
              <div className="py-6 text-center text-sm text-tinta-2">
                Nenhuma simulação.{" "}
                <button onClick={() => setAba("planejamento")} className="font-medium text-marca hover:underline">
                  Fazer o planejamento completo
                </button>
              </div>
            </Cartao>
          ) : (
            <Cartao>
              <ul className="divide-y divide-borda">
                {simulacoes.map((s) => (
                  <li key={s.id} className="flex flex-wrap items-center justify-between gap-3 py-3">
                    <button onClick={() => setAberta(aberta?.id === s.id ? null : s)} className="text-left">
                      <div className="text-sm font-medium hover:text-marca">{s.titulo}</div>
                      <div className="num text-xs text-tinta-2">
                        {dataHora(s.criado_em)} · {s.tipo === "expressa" ? "Expressa" : "Completa"} · economia de {brl(s.resultado.economia_vs_pior)}/ano
                      </div>
                    </button>
                    <div className="flex gap-2">
                      <Botao variante="fantasma" onClick={() => setAberta(aberta?.id === s.id ? null : s)}>
                        {aberta?.id === s.id ? "Fechar" : "Ver"}
                      </Botao>
                      <a href={urlProposta(s.id)} target="_blank" className="inline-flex h-10 items-center rounded-lg border border-borda px-3 text-sm font-medium hover:bg-fundo">
                        PDF
                      </a>
                      <Botao variante="fantasma" onClick={() => excluirSimulacao(s)} aria-label="Excluir simulação">
                        Excluir
                      </Botao>
                    </div>
                  </li>
                ))}
              </ul>
            </Cartao>
          )}
          {aberta && (
            <ResultadoComparativo
              resultado={aberta.resultado}
              acoes={
                <a href={urlProposta(aberta.id)} target="_blank" className="inline-flex h-10 items-center rounded-lg bg-marca px-4 text-sm font-medium text-white">
                  Abrir proposta em PDF
                </a>
              }
            />
          )}
        </div>
      )}

      {aba === "planejamento" && (
        <Cartao titulo="Planejamento tributário completo (valores anuais)">
          <FormCompleta atividadeInicial={cliente.atividade} onCalcular={calcular} carregando={calculando} />
        </Cartao>
      )}

      {aba === "dados" && (
        <div className="flex flex-col gap-4">
          <Cartao>
            <FormCliente
              inicial={cliente}
              textoBotao="Salvar alterações"
              onSalvar={async (dados) => {
                setCliente(await api<Cliente>(`/clientes/${cliente.id}`, { method: "PATCH", json: dados }));
                setAba("simulacoes");
              }}
            />
          </Cartao>
          <div>
            <Botao variante="perigo" onClick={excluirCliente}>Excluir cliente</Botao>
          </div>
        </div>
      )}
    </>
  );
}
