"use client";

import { useState } from "react";

import { type Atividade, type CompletaEntrada } from "@/lib/tipos";

import { CampoMoeda, CampoPercentual } from "./CampoMoeda";
import { ConversorDeMoeda } from "./ConversorDeMoeda";
import { SelecaoAtividade } from "./SelecaoAtividade";
import { Botao, MensagemErro, Selecao } from "./ui";

/** Planejamento completo: valores anuais com compras, despesas e alíquotas locais. */
export function FormCompleta({
  atividadeInicial,
  inicial,
  onCalcular,
  carregando,
}: {
  atividadeInicial: Atividade | null;
  inicial?: Partial<CompletaEntrada>;
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
    receita_exterior_anual: 0,
    variacao_cambial_anual: 0,
    ...inicial,
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
        if ((f.receita_exterior_anual ?? 0) > f.receita_bruta_anual) {
          return setErro("A receita do exterior não pode passar da receita bruta anual (ela é uma parte dela).");
        }
        onCalcular(f);
      }}
    >
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <SelecaoAtividade name="atividade_completa" value={f.atividade} onChange={(v) => set("atividade")((v || "servico_fator_r") as Atividade)} />
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
      <details className="rounded-lg border border-borda p-3" open={(f.receita_exterior_anual ?? 0) > 0 || (f.variacao_cambial_anual ?? 0) !== 0} data-testid="bloco-exterior">
        <summary className="cursor-pointer text-sm font-medium">
          Receita do exterior (exportação) e variação cambial
          <span className="ml-2 text-xs font-normal text-tinta-2">Opcional: para quem recebe de clientes fora do Brasil</span>
        </summary>
        <div className="mt-3 flex flex-col gap-4">
          <p className="text-xs text-tinta-2">
            {mercadoria
              ? "Exportação de mercadorias fica sem ICMS, IPI e PIS/Cofins. "
              : "Serviço prestado a cliente no exterior, com resultado verificado lá e pagamento em divisas, fica sem ISS e sem PIS/Cofins. "}
            IRPJ, CSLL e a parte previdenciária continuam. A receita do exterior é <strong>uma parte</strong> da receita bruta anual acima.
          </p>
          <div className="grid gap-4 sm:grid-cols-2">
            <CampoMoeda
              id="receita_exterior"
              rotulo={mercadoria ? "Receita de exportação de mercadorias" : "Receita de exportação de serviços"}
              valor={f.receita_exterior_anual ?? 0}
              onChange={set("receita_exterior_anual")}
              ajuda="Em reais. Se recebeu em moeda estrangeira, converta abaixo."
            />
            <div className="grid grid-cols-[110px_1fr] gap-2">
              <Selecao
                rotulo="Variação cambial"
                name="tipo_cambial"
                value={(f.variacao_cambial_anual ?? 0) < 0 ? "perda" : "ganho"}
                onChange={(e) => set("variacao_cambial_anual")(e.target.value === "perda" ? -Math.abs(f.variacao_cambial_anual ?? 0) : Math.abs(f.variacao_cambial_anual ?? 0))}
              >
                <option value="ganho">Ganho</option>
                <option value="perda">Perda</option>
              </Selecao>
              <CampoMoeda
                id="variacao_cambial"
                rotulo="Valor no ano"
                valor={Math.abs(f.variacao_cambial_anual ?? 0)}
                onChange={(v) => set("variacao_cambial_anual")((f.variacao_cambial_anual ?? 0) < 0 ? -v : v)}
              />
            </div>
          </div>
          <p className="-mt-2 text-xs text-tinta-2">
            Variação cambial: diferença entre a taxa do dia da nota e a do recebimento (líquida do ano). No Lucro Presumido o ganho
            soma na base de IRPJ e CSLL; no Lucro Real, ganho soma e perda deduz.
          </p>
          <ConversorDeMoeda onUsar={(reais) => set("receita_exterior_anual")(reais)} />
        </div>
      </details>
      <MensagemErro>{erro}</MensagemErro>
      <div>
        <Botao type="submit" carregando={carregando}>Calcular e salvar planejamento</Botao>
      </div>
    </form>
  );
}
