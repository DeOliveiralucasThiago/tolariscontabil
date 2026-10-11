"use client";

import { useState } from "react";

import { ATIVIDADES, type Atividade, type CompletaEntrada } from "@/lib/tipos";

import { CampoMoeda, CampoPercentual } from "./CampoMoeda";
import { Botao, MensagemErro, Selecao } from "./ui";

/** Planejamento completo: valores anuais com compras, despesas e alíquotas locais. */
export function FormCompleta({
  atividadeInicial,
  onCalcular,
  carregando,
}: {
  atividadeInicial: Atividade | null;
  onCalcular: (e: CompletaEntrada) => void;
  carregando: boolean;
}) {
  const [f, setF] = useState<CompletaEntrada>({
    atividade: atividadeInicial ?? "servico_fator_r",
    receita_bruta_anual: 0,
    folha_clt_anual: 0,
    pro_labore_anual: 0,
    compras_anual: 0,
    despesas_creditaveis_anual: 0,
    outras_despesas_anual: 0,
    aliquota_iss: 0.05,
    aliquota_icms: 0.18,
  });
  const [erro, setErro] = useState("");
  const mercadoria = f.atividade === "comercio" || f.atividade === "industria";
  const set = <K extends keyof CompletaEntrada>(k: K) => (v: CompletaEntrada[K]) => setF((x) => ({ ...x, [k]: v }));

  return (
    <form
      className="flex flex-col gap-4"
      onSubmit={(e) => {
        e.preventDefault();
        setErro("");
        if (f.receita_bruta_anual <= 0) return setErro("Informe a receita bruta anual.");
        onCalcular(f);
      }}
    >
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <Selecao rotulo="Atividade" name="atividade_completa" value={f.atividade} onChange={(e) => set("atividade")(e.target.value as Atividade)}>
          {ATIVIDADES.map((a) => (
            <option key={a.valor} value={a.valor}>{a.rotulo}</option>
          ))}
        </Selecao>
        <CampoMoeda id="receita" rotulo="Receita bruta anual" valor={f.receita_bruta_anual} onChange={set("receita_bruta_anual")} obrigatorio />
        <CampoMoeda id="folha_anual" rotulo="Folha CLT anual" valor={f.folha_clt_anual} onChange={set("folha_clt_anual")} ajuda="Salários brutos, sem encargos." />
        <CampoMoeda id="prolabore_anual" rotulo="Pró-labore anual" valor={f.pro_labore_anual} onChange={set("pro_labore_anual")} />
        <CampoMoeda
          id="compras"
          rotulo={mercadoria ? "Compras de mercadorias/insumos" : "Insumos e materiais"}
          valor={f.compras_anual}
          onChange={set("compras_anual")}
          ajuda="Geram crédito de ICMS e de PIS/Cofins (Lucro Real)."
        />
        <CampoMoeda
          id="desp_cred"
          rotulo="Despesas com crédito de PIS/Cofins"
          valor={f.despesas_creditaveis_anual}
          onChange={set("despesas_creditaveis_anual")}
          ajuda="Energia, aluguel pago a PJ, depreciação…"
        />
        <CampoMoeda id="outras" rotulo="Outras despesas dedutíveis" valor={f.outras_despesas_anual} onChange={set("outras_despesas_anual")} />
        {mercadoria ? (
          <CampoPercentual id="icms" rotulo="Alíquota de ICMS" valor={f.aliquota_icms} onChange={set("aliquota_icms")} max={35} />
        ) : (
          <CampoPercentual id="iss" rotulo="Alíquota de ISS do município" valor={f.aliquota_iss} onChange={set("aliquota_iss")} max={5} ajuda="Entre 2% e 5%." />
        )}
      </div>
      <MensagemErro>{erro}</MensagemErro>
      <div>
        <Botao type="submit" carregando={carregando}>Calcular e salvar planejamento</Botao>
      </div>
    </form>
  );
}
