"use client";

import { useParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import { PropostaNoPortal, type HonorariosPublico } from "@/components/PropostaNoPortal";
import { ResultadoSimulacao } from "@/components/ResultadoSimulacao";
import { aplicarCorMarca } from "@/components/Sessao";
import { api, ErroApi } from "@/lib/api";
import { data } from "@/lib/formato";
import { ROTULO_TIPO, type Simulacao, type TipoSimulacao } from "@/lib/tipos";

interface Portal {
  escritorio: {
    nome: string;
    cor_primaria: string;
    tem_logo: boolean;
    email: string | null;
    telefone: string | null;
    contador_responsavel: string | null;
    crc: string | null;
  };
  cliente: string;
  simulacoes: {
    id: number;
    tipo: TipoSimulacao;
    titulo: string;
    resultado: Simulacao["resultado"];
    criado_em: string;
    honorarios: HonorariosPublico | null;
    aceite_em: string | null;
    aceite_nome: string | null;
  }[];
}

export default function PaginaPortal() {
  const { token } = useParams<{ token: string }>();
  const [portal, setPortal] = useState<Portal | null>(null);
  const [erro, setErro] = useState("");
  const [aberta, setAberta] = useState<number | null>(null);
  const base = `/api/portal/${encodeURIComponent(token)}`;
  const avisados = useRef(new Set<number>());

  const carregar = useCallback(
    (primeira: boolean) =>
      api<Portal>(`/portal/${encodeURIComponent(token)}`)
        .then((p) => {
          aplicarCorMarca(p.escritorio.cor_primaria);
          setPortal(p);
          if (primeira && p.simulacoes.length === 1) setAberta(p.simulacoes[0].id);
        })
        .catch((e) => setErro(e instanceof ErroApi && e.status === 404 ? "Este link não está mais ativo. Peça um novo ao seu escritório contábil." : "Não foi possível abrir o portal.")),
    [token],
  );

  useEffect(() => {
    carregar(true);
  }, [carregar]);

  // Confirmação de leitura: avisa o escritório uma vez por relatório aberto nesta visita
  useEffect(() => {
    if (aberta == null || avisados.current.has(aberta)) return;
    avisados.current.add(aberta);
    api(`/portal/${encodeURIComponent(token)}/simulacoes/${aberta}/visto`, { method: "POST" }).catch(() => undefined);
  }, [aberta, token]);

  if (!portal) {
    return (
      <div className="grid min-h-[calc(100vh-var(--faixa))] place-items-center p-6 text-center text-sm text-tinta-2">
        {erro || "Carregando…"}
      </div>
    );
  }

  const esc = portal.escritorio;
  const atual = portal.simulacoes.find((s) => s.id === aberta);

  return (
    <div className="min-h-[calc(100vh-var(--faixa))]">
      <header className="bg-marca text-white">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-4 px-4 py-5 sm:px-8">
          <div className="flex items-center gap-3">
            {esc.tem_logo && (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={`${base}/logo`} alt="" className="h-11 max-w-40 rounded bg-white object-contain p-1" />
            )}
            <div>
              <div className="text-lg font-semibold">{esc.nome}</div>
              <div className="text-xs text-white/80">Portal do cliente</div>
            </div>
          </div>
          <div className="text-right text-xs text-white/85">
            {esc.email && <div>{esc.email}</div>}
            {esc.telefone && <div>{esc.telefone}</div>}
          </div>
        </div>
      </header>

      <main className="mx-auto w-full max-w-6xl px-4 py-6 sm:px-8 sm:py-8">
        <h1 className="text-2xl font-semibold tracking-tight">{portal.cliente}</h1>
        <p className="mt-1 text-sm text-tinta-2">Relatórios preparados por {esc.contador_responsavel ?? esc.nome}{esc.crc ? ` · CRC ${esc.crc}` : ""}.</p>

        {portal.simulacoes.length === 0 ? (
          <div className="mt-6 rounded-xl border border-dashed border-borda bg-superficie p-8 text-center text-sm text-tinta-2">
            Ainda não há relatórios publicados. Seu escritório avisará quando houver novidades.
          </div>
        ) : (
          <ul className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {portal.simulacoes.map((s) => (
              <li key={s.id}>
                <div className={`flex h-full flex-col justify-between gap-3 rounded-xl border bg-superficie p-4 ${aberta === s.id ? "border-marca ring-1 ring-marca" : "border-borda"}`}>
                  <div>
                    <div className="text-xs font-medium uppercase tracking-wide text-tinta-2">{ROTULO_TIPO[s.tipo] ?? s.tipo}</div>
                    <div className="mt-1 font-semibold">{s.titulo}</div>
                    <div className="num text-xs text-tinta-2">{data(s.criado_em)}</div>
                    {s.honorarios && (
                      <div className="mt-1 text-xs font-medium text-marca">
                        {s.aceite_em ? "Proposta de honorários aceita" : s.honorarios.expirada ? "Proposta de honorários vencida" : "Proposta de honorários para sua análise"}
                      </div>
                    )}
                  </div>
                  <div className="flex gap-2">
                    <button
                      onClick={() => setAberta(aberta === s.id ? null : s.id)}
                      className="h-9 rounded-lg border border-borda px-3 text-sm font-medium hover:bg-fundo"
                    >
                      {aberta === s.id ? "Fechar" : "Ver"}
                    </button>
                    <a href={`${base}/simulacoes/${s.id}.pdf`} target="_blank" rel="noreferrer" className="inline-flex h-9 items-center rounded-lg bg-marca px-3 text-sm font-medium text-white">
                      Baixar PDF
                    </a>
                  </div>
                </div>
              </li>
            ))}
          </ul>
        )}

        {atual && (
          <div className="mt-6 flex flex-col gap-4">
            {atual.honorarios && (
              <PropostaNoPortal
                token={token}
                simulacaoId={atual.id}
                cliente={portal.cliente}
                honorarios={atual.honorarios}
                aceiteEm={atual.aceite_em}
                aceiteNome={atual.aceite_nome}
                onAceita={() => carregar(false)}
              />
            )}
            <ResultadoSimulacao
              sim={{ ...atual, honorarios: null, cliente_id: 0, entrada: {}, versao_motor: "", publicada: true }}
            />
          </div>
        )}

        <p className="mt-10 text-center text-xs text-tinta-2">
          Estimativas elaboradas pelo seu escritório contábil; não substituem a apuração oficial. · Tolaris Contábil
        </p>
      </main>
    </div>
  );
}
