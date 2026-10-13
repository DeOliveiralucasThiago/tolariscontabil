"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { api } from "@/lib/api";
import { brl } from "@/lib/formato";
import type { RespostaAvisos } from "@/lib/tipos";

import { ChipGravidade } from "./Gravidade";
import { Cartao } from "./ui";

/** Resumo dos avisos da carteira no painel: carrega em segundo plano para não atrasar a tela. */
export function AvisosNoPainel() {
  const [dados, setDados] = useState<RespostaAvisos | null>(null);
  const [falhou, setFalhou] = useState(false);

  useEffect(() => {
    api<RespostaAvisos>("/avisos").then(setDados).catch(() => setFalhou(true));
  }, []);

  if (falhou) return null;
  return (
    <Cartao
      titulo="Avisos da carteira"
      acoes={
        <Link href="/avisos" className="text-sm font-medium text-marca hover:underline">
          Ver todos
        </Link>
      }
    >
      {!dados ? (
        <p className="text-sm text-tinta-2">Verificando a carteira…</p>
      ) : dados.avisos.length === 0 ? (
        <p className="text-sm text-tinta-2">Nenhum aviso agora. Fator R, limites de receita e mudanças de regra são acompanhados automaticamente.</p>
      ) : (
        <div className="flex flex-col gap-3">
          <p className="text-sm text-tinta-2">
            {dados.resumo.critico} {dados.resumo.critico === 1 ? "crítico" : "críticos"} · {dados.resumo.atencao} em atenção ·{" "}
            {dados.resumo.oportunidade} {dados.resumo.oportunidade === 1 ? "oportunidade" : "oportunidades"}
            {dados.resumo.valor_oportunidades > 0 && <> ({brl(dados.resumo.valor_oportunidades)} a ganhar)</>}
          </p>
          <ul className="divide-y divide-borda">
            {dados.avisos.slice(0, 3).map((a) => (
              <li key={a.id} className="flex flex-wrap items-center gap-2 py-2 text-sm">
                <ChipGravidade gravidade={a.gravidade} />
                <Link href={`/clientes/${a.cliente_id}`} className="font-medium hover:text-marca">
                  {a.cliente}
                </Link>
                <span className="text-tinta-2">{a.titulo}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </Cartao>
  );
}
