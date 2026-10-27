"use client";

import { useEffect, useState } from "react";

import { api } from "@/lib/api";
import type { NaturezaInfo } from "@/lib/tipos";

import { Etiqueta, Selecao } from "./ui";

/** Descrições como a Receita as grava no CNPJ; a lista cobre as naturezas mais comuns e a do cadastro entra à parte quando é outra. */
const OPCOES = [
  "Empresário (Individual)",
  "Sociedade Empresária Limitada",
  "Sociedade Simples Pura",
  "Sociedade Simples Limitada",
  "Sociedade Unipessoal de Advogados",
  "Empresa Individual de Responsabilidade Limitada (de Natureza Empresária)",
  "Sociedade Anônima Fechada",
  "Sociedade Anônima Aberta",
  "Cooperativa",
  "Cooperativa de Consumo",
  "Associação Privada",
  "Fundação Privada",
];

const TOM: Record<NaturezaInfo["simples"], string> = { sim: "ativo", vedado: "perigo", nao_se_aplica: "perigo", conferir: "atencao" };
const TEXTO: Record<NaturezaInfo["simples"], string> = {
  sim: "Pode optar pelo Simples",
  vedado: "Simples vedado",
  nao_se_aplica: "Simples não se aplica",
  conferir: "Conferir",
};

/** Natureza jurídica do cadastro (vem da consulta de CNPJ) e o que ela permite no Simples Nacional e no MEI. */
export function SeletorNatureza({
  valor,
  onChange,
  id = "natureza_juridica",
  rotulo = "Natureza jurídica",
}: {
  valor: string;
  onChange: (descricao: string) => void;
  id?: string;
  rotulo?: string;
}) {
  const [info, setInfo] = useState<NaturezaInfo | null>(null);
  useEffect(() => {
    let vivo = true;
    if (!valor) {
      setInfo(null);
      return;
    }
    api<NaturezaInfo | null>(`/cnpj/natureza/classificar?descricao=${encodeURIComponent(valor)}`)
      .then((r) => vivo && setInfo(r))
      .catch(() => vivo && setInfo(null));
    return () => {
      vivo = false;
    };
  }, [valor]);
  const opcoes = valor && !OPCOES.includes(valor) ? [valor, ...OPCOES] : OPCOES;
  return (
    <div className="flex flex-col gap-2" data-testid="natureza-juridica">
      <Selecao id={id} name={id} rotulo={rotulo} value={valor} onChange={(e) => onChange(e.target.value)}>
        <option value="">Não informada</option>
        {opcoes.map((o) => (
          <option key={o} value={o}>{o}</option>
        ))}
      </Selecao>
      {info && (
        <div className="rounded-lg border border-borda bg-superficie p-3 text-xs text-tinta-2" data-testid="natureza-info">
          <div className="mb-1 flex flex-wrap items-center gap-2">
            <Etiqueta tom={TOM[info.simples]}>{TEXTO[info.simples]}</Etiqueta>
            {info.mei && <Etiqueta tom="ativo">Pode ser MEI</Etiqueta>}
          </div>
          {info.explicacao} <span className="whitespace-nowrap">({info.base_legal})</span>
        </div>
      )}
    </div>
  );
}
