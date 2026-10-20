"use client";

import type { ReactNode } from "react";

import { ATIVIDADES, NOTA_ANEXO_V, type Atividade } from "@/lib/tipos";

import { Selecao } from "./ui";

/** Seletor de atividade com o Anexo no nome de cada opção e, embaixo, exemplos e como o Simples decide. */
export function SelecaoAtividade({
  value,
  onChange,
  name = "atividade",
  rotulo = "Atividade",
  vazio,
  ajuda,
}: {
  value: Atividade | "";
  onChange: (v: Atividade | "") => void;
  name?: string;
  rotulo?: string;
  /** Texto da opção em branco (ex.: "Selecione…"); sem ele, não há opção em branco. */
  vazio?: string;
  /** Texto próprio acima da explicação (ex.: a justificativa da sugestão pelo CNAE). */
  ajuda?: ReactNode;
}) {
  const info = ATIVIDADES.find((a) => a.valor === value);
  return (
    <div>
      <Selecao rotulo={rotulo} name={name} value={value} onChange={(e) => onChange(e.target.value as Atividade | "")} ajuda={ajuda}>
        {vazio && <option value="">{vazio}</option>}
        {ATIVIDADES.map((a) => (
          <option key={a.valor} value={a.valor}>
            {a.rotuloLongo}
          </option>
        ))}
      </Selecao>
      {info && (
        <details className="mt-1.5 rounded-lg border border-borda bg-fundo px-3 py-2 text-xs text-tinta-2" data-testid={`explica-${name}`}>
          <summary className="cursor-pointer font-medium text-tinta">O que entra em “{info.rotulo}”?</summary>
          <p className="mt-1.5">
            <strong className="text-tinta">Exemplos:</strong> {info.exemplos}
          </p>
          <p className="mt-1">
            <strong className="text-tinta">Como é calculado:</strong> {info.como}
          </p>
          <p className="mt-1">{NOTA_ANEXO_V}</p>
        </details>
      )}
    </div>
  );
}
