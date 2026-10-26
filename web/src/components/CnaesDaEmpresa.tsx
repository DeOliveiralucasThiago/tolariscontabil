"use client";

import type { CnaesDoCliente } from "@/lib/tipos";

import { SeloConfianca } from "./BuscaCnae";
import { Cartao } from "./ui";

/** CNAEs de uma empresa (principal e secundários) com o Anexo provável de cada um, vedações e candidatos ao Anexo III. */
export function CnaesDaEmpresa({ titulo, dados }: { titulo: string; dados: CnaesDoCliente }) {
  if (!dados.cnaes.length) return null;
  return (
    <div data-testid="cnaes-do-cliente">
      <Cartao titulo={titulo}>
        <ul className="divide-y divide-borda text-sm">
          {dados.cnaes.map((c) => (
            <li key={c.codigo} className="flex flex-wrap items-baseline justify-between gap-2 py-2">
              <span>
                <span className="num font-medium">{c.codigo.replace(/^(\d{4})(\d)(\d{2})$/, "$1-$2/$3")}</span>{" "}
                {c.principal && <span className="rounded bg-fundo px-1.5 py-0.5 text-xs">principal</span>} {c.descricao}
              </span>
              <span className="flex items-center gap-1.5 text-xs text-tinta-2">
                <span className={c.vedacao === "impeditivo" ? "font-medium text-red-700" : ""}>{c.anexo}</span>
                <SeloConfianca confianca={c.confianca} />
              </span>
            </li>
          ))}
        </ul>
        {dados.atividade_fator_r && dados.anexo_iii_no_cadastro.length > 0 && (
          <p className="mt-3 rounded-lg bg-fundo p-3 text-sm" data-testid="candidatos-anexo-iii">
            <strong className="font-medium">Já no cadastro:</strong>{" "}
            {dados.anexo_iii_no_cadastro.map((c) => c.descricao || c.codigo).join("; ")} —{" "}
            {dados.anexo_iii_no_cadastro.length === 1 ? "tende a ser atividade" : "tendem a ser atividades"} do Anexo III. Se a empresa
            realmente presta esse serviço, vale simular abaixo quanto da receita ele representa.
          </p>
        )}
        {dados.vedados.length > 0 && (
          <p role="alert" className="mt-3 rounded-lg bg-red-50 p-3 text-sm text-red-800" data-testid="cnaes-vedados">
            <strong className="font-medium">Atenção:</strong> {dados.vedados.map((c) => c.descricao || c.codigo).join("; ")} —{" "}
            {dados.vedados.some((c) => c.vedacao === "impeditivo")
              ? "CNAE impeditivo ao Simples Nacional (Resolução CGSN 140/2018, Anexo VI)."
              : "CNAE ambíguo no Simples (Anexo VII): confirme se a atividade exercida permite a opção."}
          </p>
        )}
        <p className="mt-3 text-xs text-tinta-2">{dados.aviso}</p>
      </Cartao>
    </div>
  );
}
