"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { useSessao } from "@/components/Sessao";
import { BotaoLink, Cartao, MensagemErro, Titulo } from "@/components/ui";
import { api, ErroApi, urlProposta } from "@/lib/api";
import { brl, dataHora } from "@/lib/formato";
import type { Painel } from "@/lib/tipos";

function Indicador({ rotulo, valor, detalhe }: { rotulo: string; valor: string; detalhe?: string }) {
  return (
    <div className="rounded-xl border border-borda bg-superficie p-5">
      <div className="text-sm text-tinta-2">{rotulo}</div>
      <div className="num mt-1 text-3xl font-semibold">{valor}</div>
      {detalhe && <div className="mt-1 text-xs text-tinta-2">{detalhe}</div>}
    </div>
  );
}

export default function PaginaPainel() {
  const { sessao } = useSessao();
  const [painel, setPainel] = useState<Painel | null>(null);
  const [erro, setErro] = useState("");

  useEffect(() => {
    api<Painel>("/painel")
      .then(setPainel)
      .catch((e) => setErro(e instanceof ErroApi ? e.message : "Falha ao carregar o painel"));
  }, []);

  return (
    <>
      <Titulo
        sub={`Bem-vindo(a), ${sessao.usuario.nome.split(" ")[0]}.`}
        acoes={<BotaoLink href="/prospeccao">Nova prospecção</BotaoLink>}
      >
        Painel
      </Titulo>
      <MensagemErro>{erro}</MensagemErro>
      {painel && (
        <div className="flex flex-col gap-6">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Indicador rotulo="Clientes ativos" valor={String(painel.clientes_ativos)} />
            <Indicador rotulo="Prospects" valor={String(painel.prospects)} />
            <Indicador rotulo="Simulações no mês" valor={String(painel.simulacoes_mes)} />
            <Indicador
              rotulo="Economia identificada no mês"
              valor={brl(painel.economia_identificada_mes)}
              detalhe="Potencial anual somado, uma simulação (a mais recente) por cliente"
            />
          </div>

          <Cartao titulo="Últimas simulações">
            {painel.ultimas_simulacoes.length === 0 ? (
              <div className="py-8 text-center text-sm text-tinta-2">
                Nenhuma simulação ainda.{" "}
                <Link href="/prospeccao" className="font-medium text-marca hover:underline">
                  Faça a primeira em 2 minutos
                </Link>
                .
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full min-w-[560px] text-sm">
                  <thead>
                    <tr className="border-b border-borda text-left text-xs text-tinta-2">
                      <th className="py-2 font-medium">Cliente</th>
                      <th className="py-2 font-medium">Recomendado</th>
                      <th className="py-2 text-right font-medium">Economia/ano</th>
                      <th className="py-2 text-right font-medium">Data</th>
                      <th className="py-2" />
                    </tr>
                  </thead>
                  <tbody>
                    {painel.ultimas_simulacoes.map((s) => (
                      <tr key={s.id} className="border-b border-borda/70">
                        <td className="py-2">
                          <Link href={`/clientes/${s.cliente_id}`} className="font-medium hover:text-marca">
                            {s.cliente}
                          </Link>
                        </td>
                        <td className="py-2">{s.melhor}</td>
                        <td className="num py-2 text-right">{brl(s.economia)}</td>
                        <td className="num py-2 text-right text-tinta-2">{dataHora(s.criado_em)}</td>
                        <td className="py-2 text-right">
                          <a href={urlProposta(s.id)} target="_blank" className="text-xs font-medium text-marca hover:underline">
                            PDF
                          </a>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Cartao>
        </div>
      )}
    </>
  );
}
