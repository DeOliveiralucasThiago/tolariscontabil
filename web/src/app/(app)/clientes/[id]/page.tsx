"use client";

import Link from "next/link";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useState } from "react";

import { EnviarRelatorio } from "@/components/EnviarRelatorio";
import { FormCliente } from "@/components/FormCliente";
import { FormCompleta } from "@/components/FormCompleta";
import { Acompanhamento } from "@/components/Acompanhamento";
import { MovimentoFiscal } from "@/components/MovimentoFiscal";
import { PortalCliente } from "@/components/PortalCliente";
import { PropostaHonorarios } from "@/components/PropostaHonorarios";
import { useSessao } from "@/components/Sessao";
import { ResultadoSimulacao } from "@/components/ResultadoSimulacao";
import { Abas, Botao, BotaoLink, Cartao, Etiqueta, MensagemErro, Titulo } from "@/components/ui";
import { api, ErroApi, urlProposta } from "@/lib/api";
import { brl, dataHora, mascaraCnpj } from "@/lib/formato";
import {
  ROTULO_ATIVIDADE,
  ROTULO_REGIME,
  ROTULO_STATUS,
  ROTULO_TIPO,
  type Cliente,
  type CompletaEntrada,
  type Simulacao,
} from "@/lib/tipos";

type Aba = "simulacoes" | "planejamento" | "movimento" | "acompanhamento" | "dados";
const ABAS: Aba[] = ["simulacoes", "planejamento", "movimento", "acompanhamento", "dados"];

export default function DetalheCliente() {
  return (
    <Suspense>
      <DetalheClienteConteudo />
    </Suspense>
  );
}

/** Linha de situação de um relatório: publicado no portal, visto pelo cliente, proposta e aceite. */
function StatusDoRelatorio({ sim }: { sim: Simulacao }) {
  const itens: { texto: string; tom: "ok" | "neutro" | "alerta" }[] = [];
  if (sim.publicada) {
    itens.push(
      sim.visto_primeira_em
        ? { texto: `Visto pelo cliente em ${dataHora(sim.visto_ultima_em)} · ${sim.aberturas} ${sim.aberturas === 1 ? "abertura" : "aberturas"}`, tom: "ok" }
        : { texto: "No portal · ainda não visto pelo cliente", tom: "neutro" },
    );
  }
  if (sim.honorarios) {
    itens.push({ texto: `Honorários ${brl(sim.honorarios.valor_mensal)}/mês`, tom: "neutro" });
    if (sim.aceite_em) itens.push({ texto: `Proposta aceita por ${sim.aceite_nome} em ${dataHora(sim.aceite_em)}`, tom: "ok" });
  }
  if (!itens.length) return null;
  const cor = { ok: "text-emerald-700", neutro: "text-tinta-2", alerta: "text-amber-700" };
  return (
    <ul className="mt-1 flex flex-wrap gap-x-4 gap-y-0.5 text-xs">
      {itens.map((i) => (
        <li key={i.texto} className={cor[i.tom]}>
          {i.tom === "ok" ? "✓ " : "• "}
          {i.texto}
        </li>
      ))}
    </ul>
  );
}

function DetalheClienteConteudo() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const abaPedida = useSearchParams().get("aba");
  const [cliente, setCliente] = useState<Cliente | null>(null);
  const [simulacoes, setSimulacoes] = useState<Simulacao[]>([]);
  const [aberta, setAberta] = useState<Simulacao | null>(null);
  const [aba, setAba] = useState<Aba>(ABAS.find((a) => a === abaPedida) ?? "simulacoes");
  const [recalculandoId, setRecalculandoId] = useState<number | null>(null);
  const [erro, setErro] = useState("");
  const [calculando, setCalculando] = useState(false);
  const [enviandoId, setEnviandoId] = useState<number | null>(null);
  const [honorariosId, setHonorariosId] = useState<number | null>(null);
  const { sessao } = useSessao();
  const [versaoPortal, setVersaoPortal] = useState(0);
  const [planejamentoInicial, setPlanejamentoInicial] = useState<{ valores: Partial<CompletaEntrada>; texto: string } | null>(null);

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

  async function recalcular(sim: Simulacao) {
    setErro("");
    setRecalculandoId(sim.id);
    try {
      const nova = await api<Simulacao>(`/simulacoes/${sim.id}/recalcular`, { method: "POST" });
      setSimulacoes((s) => [nova, ...s]);
      setAberta(nova);
    } catch (e) {
      setErro(e instanceof ErroApi ? e.message : "Não foi possível recalcular");
    } finally {
      setRecalculandoId(null);
    }
  }

  async function alternarPublicacao(sim: Simulacao) {
    const publicada = !sim.publicada;
    const marcar = (valor: boolean) => setSimulacoes((lista) => lista.map((x) => (x.id === sim.id ? { ...x, publicada: valor } : x)));
    marcar(publicada); // resposta imediata na tela; desfaz se a API falhar
    try {
      await api(`/simulacoes/${sim.id}/publicacao`, { method: "PATCH", json: { publicada } });
      setVersaoPortal((v) => v + 1);
    } catch (e) {
      marcar(!publicada);
      setErro(e instanceof ErroApi ? e.message : "Não foi possível alterar a publicação");
    }
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
    { id: "movimento", rotulo: "Movimento fiscal" },
    { id: "acompanhamento", rotulo: "Acompanhamento" },
    { id: "dados", rotulo: "Dados cadastrais" },
  ];

  return (
    <>
      <div className="mb-2 text-sm">
        <Link href="/clientes" className="text-tinta-2 hover:text-tinta">← Clientes</Link>
      </div>
      <Titulo
        acoes={
          <>
            <BotaoLink variante="secundario" href={`/reforma?cliente=${cliente.id}`}>Reforma Tributária</BotaoLink>
            <BotaoLink variante="secundario" href={`/pessoa-fisica?cliente=${cliente.id}&aba=prolabore`}>Pró-labore</BotaoLink>
          </>
        }
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

      <Abas abas={abas} ativa={aba} onChange={setAba} />
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
                  <li key={s.id} className="py-3">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div className="min-w-0">
                    <button onClick={() => setAberta(aberta?.id === s.id ? null : s)} className="text-left">
                      <div className="text-sm font-medium hover:text-marca">{s.titulo}</div>
                      <div className="num text-xs text-tinta-2">
                        {dataHora(s.criado_em)} · {ROTULO_TIPO[s.tipo] ?? s.tipo}
                        {s.resultado.economia_vs_pior > 0 && <> · economia de {brl(s.resultado.economia_vs_pior)}/ano</>}
                      </div>
                    </button>
                    <StatusDoRelatorio sim={s} />
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                      <label className="mr-1 flex items-center gap-1.5 text-xs text-tinta-2" title="Visível no portal do cliente">
                        <input
                          type="checkbox"
                          checked={s.publicada}
                          onChange={() => alternarPublicacao(s)}
                          aria-label={`Publicar no portal: ${s.titulo}`}
                          className="accent-[var(--marca)]"
                        />
                        No portal
                      </label>
                      <Botao variante="fantasma" onClick={() => setAberta(aberta?.id === s.id ? null : s)}>
                        {aberta?.id === s.id ? "Fechar" : "Ver"}
                      </Botao>
                      <a href={urlProposta(s.id)} target="_blank" className="inline-flex h-10 items-center rounded-lg border border-borda px-3 text-sm font-medium hover:bg-fundo">
                        PDF
                      </a>
                      <Botao variante="secundario" onClick={() => setEnviandoId(enviandoId === s.id ? null : s.id)}>
                        Enviar
                      </Botao>
                      <Botao variante="fantasma" onClick={() => setHonorariosId(honorariosId === s.id ? null : s.id)}>
                        Honorários
                      </Botao>
                      <Botao variante="fantasma" onClick={() => recalcular(s)} carregando={recalculandoId === s.id} title="Refazer com as regras atuais">
                        Recalcular
                      </Botao>
                      <Botao variante="fantasma" onClick={() => excluirSimulacao(s)} aria-label="Excluir simulação">
                        Excluir
                      </Botao>
                    </div>
                  </div>
                  {honorariosId === s.id && (
                    <PropostaHonorarios
                      sim={s}
                      onAtualizada={(nova) => setSimulacoes((lista) => lista.map((x) => (x.id === nova.id ? { ...x, ...nova } : x)))}
                      onFechar={() => setHonorariosId(null)}
                    />
                  )}
                  {enviandoId === s.id && (
                    <EnviarRelatorio simulacaoId={s.id} emailCliente={cliente.email} onFechar={() => setEnviandoId(null)} />
                  )}
                  </li>
                ))}
              </ul>
            </Cartao>
          )}
          <PortalCliente
            clienteId={cliente.id}
            emailCliente={cliente.email}
            telefoneCliente={cliente.telefone}
            contatoCliente={cliente.contato_nome}
            razaoSocial={cliente.razao_social}
            escritorioNome={sessao.escritorio.nome}
            versao={versaoPortal}
          />
          {aberta && (
            <ResultadoSimulacao
              sim={aberta}
              acoes={
                <a href={urlProposta(aberta.id)} target="_blank" className="inline-flex h-10 items-center rounded-lg bg-marca px-4 text-sm font-medium text-white">
                  Abrir relatório em PDF
                </a>
              }
            />
          )}
        </div>
      )}

      {aba === "planejamento" && (
        <Cartao titulo="Planejamento tributário completo (valores anuais)">
          {planejamentoInicial && (
            <p className="mb-4 rounded-lg bg-fundo px-3 py-2 text-xs text-tinta-2">
              {planejamentoInicial.texto}
            </p>
          )}
          <FormCompleta
            key={planejamentoInicial ? JSON.stringify(planejamentoInicial.valores) : "vazio"}
            atividadeInicial={cliente.atividade}
            inicial={planejamentoInicial?.valores}
            onCalcular={calcular}
            carregando={calculando}
          />
        </Cartao>
      )}

      {aba === "movimento" && (
        <MovimentoFiscal
          clienteId={cliente.id}
          temCnpj={Boolean(cliente.cnpj)}
          cliente={cliente}
          onRecuperacaoSalva={(sim) => setSimulacoes((s) => [sim, ...s])}
          onUsarNoPlanejamento={(receita, compras) => {
            setPlanejamentoInicial({
              valores: { receita_bruta_anual: Math.round(receita * 100) / 100, compras_anual: Math.round(compras * 100) / 100 },
              texto: "Receita e compras preenchidas com o movimento fiscal importado. Complete folha, pró-labore e despesas.",
            });
            setAba("planejamento");
          }}
          onUsarPlanilha={(valores, texto) => {
            setPlanejamentoInicial({ valores, texto });
            setAba("planejamento");
          }}
        />
      )}

      {aba === "acompanhamento" && (
        <Acompanhamento
          clienteId={cliente.id}
          versao={simulacoes.length}
          onUsarNoPlanejamento={(valores, texto) => {
            setPlanejamentoInicial({ valores, texto });
            setAba("planejamento");
          }}
        />
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
