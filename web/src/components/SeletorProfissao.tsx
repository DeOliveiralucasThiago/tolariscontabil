"use client";

import { PROFISSAO_OUTRA, PROFISSAO_SAUDE, PROFISSOES_ART_127, reducaoDaProfissao } from "@/lib/profissoes";

import { Selecao } from "./ui";

/** Profissão da sociedade para a redução de IBS e CBS: 30% para as 18 do art. 127 da LC 214/2025, 60% para serviços de saúde. */
export function SeletorProfissao({
  id,
  valor,
  onChange,
}: {
  id: string;
  valor: string;
  /** Devolve a profissão escolhida e a redução de alíquota que ela dá direito. */
  onChange: (profissao: string, reducao: number) => void;
}) {
  return (
    <div className="flex flex-col gap-2">
      <Selecao
        id={id}
        name={id}
        rotulo="Profissão da sociedade (redução de IBS e CBS)"
        value={valor}
        onChange={(e) => onChange(e.target.value, reducaoDaProfissao(e.target.value))}
        ajuda="A LC 214/2025 reduz 30% as alíquotas de IBS e CBS de 18 profissões regulamentadas (art. 127) e 60% as de serviços de saúde (art. 130)."
      >
        <option value="">Não informada (alíquota cheia)</option>
        <optgroup label="Redução de 30% (art. 127)">
          {PROFISSOES_ART_127.map((p) => (
            <option key={p} value={p}>{p}</option>
          ))}
        </optgroup>
        <option value={PROFISSAO_SAUDE}>Serviços de saúde do Anexo III (redução de 60%)</option>
        <option value={PROFISSAO_OUTRA}>Outra profissão (fora das listas, sem redução)</option>
      </Selecao>
      {valor && valor !== PROFISSAO_SAUDE && valor !== PROFISSAO_OUTRA && (
        <p className="rounded-lg border border-borda bg-superficie p-3 text-xs text-tinta-2" data-testid="requisitos-art-127">
          Para a sociedade ter a redução, o art. 127, § 1º, II, exige <strong>todos</strong> estes requisitos: sócios com habilitação ligada ao
          objeto e sob fiscalização de conselho; nenhum sócio pessoa jurídica; a sociedade não é sócia de outra pessoa jurídica; nenhuma atividade
          diferente das habilitações dos sócios; e serviços da atividade-fim prestados diretamente pelos sócios (com auxiliares). A natureza jurídica
          e a distribuição de lucros não impedem. Confirme o enquadramento.
        </p>
      )}
      {valor === PROFISSAO_OUTRA && (
        <p className="text-xs text-tinta-2">Medicina humana, odontologia, psicologia e outras profissões não estão na lista de 30%.</p>
      )}
      {valor === PROFISSAO_SAUDE && (
        <p className="text-xs text-tinta-2">Só vale para os serviços de saúde que constam do Anexo III da LC 214/2025 (classificação NBS). Confirme o serviço.</p>
      )}
    </div>
  );
}
