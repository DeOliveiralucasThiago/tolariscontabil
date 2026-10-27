"use client";

import { useState } from "react";

import { type Atividade, type CompletaEntrada } from "@/lib/tipos";

import { CampoMoeda, CampoPercentual } from "./CampoMoeda";
import { ConversorDeMoeda } from "./ConversorDeMoeda";
import { SelecaoAtividade } from "./SelecaoAtividade";
import { Botao, Campo, MensagemErro, Selecao } from "./ui";

/** Planejamento completo: valores anuais com compras, despesas e alíquotas locais. */
export function FormCompleta({
  atividadeInicial,
  inicial,
  onCalcular,
  carregando,
  rotuloBotao = "Calcular e salvar planejamento",
  mostrarAnexoIII = true,
}: {
  atividadeInicial: Atividade | null;
  inicial?: Partial<CompletaEntrada>;
  onCalcular: (e: CompletaEntrada) => void;
  carregando: boolean;
  rotuloBotao?: string;
  /** Campo da receita que já tributa no Anexo III (atividade exercida de fato); a análise de enquadramento o dispensa. */
  mostrarAnexoIII?: boolean;
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
    receita_anexo_iii_anual: 0,
    folha_fator_r_anual: null,
    sociedade_profissionais: false,
    profissionais: 0,
    iss_fixo_por_profissional_anual: 0,
    servicos_hospitalares: false,
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
        if ((f.receita_anexo_iii_anual ?? 0) > f.receita_bruta_anual) {
          return setErro("A receita do Anexo III não pode passar da receita bruta anual (ela é uma parte dela).");
        }
        if (!mercadoria && f.sociedade_profissionais && ((f.profissionais ?? 0) < 1 || (f.iss_fixo_por_profissional_anual ?? 0) <= 0)) {
          return setErro("Informe a quantidade de profissionais e o ISS fixo anual de cada um.");
        }
        onCalcular({
          ...f,
          folha_fator_r_anual: f.folha_fator_r_anual || null,
          sociedade_profissionais: !mercadoria && !!f.sociedade_profissionais,
          servicos_hospitalares: !mercadoria && !!f.servicos_hospitalares,
        });
      }}
    >
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <SelecaoAtividade name="atividade_completa" value={f.atividade} onChange={(v) => set("atividade")((v || "servico_fator_r") as Atividade)} />
        <CampoMoeda id="receita" rotulo="Receita bruta anual" valor={f.receita_bruta_anual} onChange={set("receita_bruta_anual")} obrigatorio />
        <CampoMoeda id="folha_anual" rotulo="Folha CLT anual" valor={f.folha_clt_anual} onChange={set("folha_clt_anual")} ajuda="Salários brutos, incluindo 13º e férias, sem encargos. O FGTS de 8% é somado pelo sistema." />
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
      {!mercadoria && (
        <details
          className="rounded-lg border border-borda p-3"
          open={!!f.sociedade_profissionais || !!f.servicos_hospitalares}
          data-testid="bloco-profissionais"
        >
          <summary className="cursor-pointer text-sm font-medium">
            Sociedade de profissionais (ISS fixo) e serviços hospitalares
            <span className="ml-2 text-xs font-normal text-tinta-2">Opcional: advocacia, contabilidade, medicina, clínicas</span>
          </summary>
          <div className="mt-3 flex flex-col gap-4">
            <label className="flex items-start gap-2 text-sm">
              <input
                id="sociedade_profissionais"
                type="checkbox"
                className="mt-1"
                checked={!!f.sociedade_profissionais}
                onChange={(e) => set("sociedade_profissionais")(e.target.checked)}
              />
              <span>
                Sociedade uniprofissional com ISS fixo por profissional
                <span className="block text-xs text-tinta-2">
                  No Lucro Presumido e no Lucro Real o ISS passa a ser o valor fixo anual de cada profissional (Decreto-Lei 406/1968, art. 9º),
                  em vez de uma porcentagem da receita. No Simples Nacional o ISS segue a receita, dentro do DAS.
                </span>
              </span>
            </label>
            {f.sociedade_profissionais && (
              <div className="grid gap-4 sm:grid-cols-2">
                <Campo
                  id="profissionais"
                  name="profissionais"
                  rotulo="Profissionais da sociedade"
                  type="number"
                  min={1}
                  step={1}
                  value={f.profissionais ? String(f.profissionais) : ""}
                  onChange={(e) => set("profissionais")(Math.max(0, Math.floor(Number(e.target.value) || 0)))}
                  ajuda="Sócios e profissionais habilitados que a lei do município conta para o ISS fixo."
                />
                <CampoMoeda
                  id="iss_fixo_profissional"
                  rotulo="ISS fixo anual de cada profissional"
                  valor={f.iss_fixo_por_profissional_anual ?? 0}
                  onChange={set("iss_fixo_por_profissional_anual")}
                  ajuda="Valor da lei do seu município; varia de cidade para cidade."
                />
              </div>
            )}
            <label className="flex items-start gap-2 text-sm">
              <input
                id="servicos_hospitalares"
                type="checkbox"
                className="mt-1"
                checked={!!f.servicos_hospitalares}
                onChange={(e) => set("servicos_hospitalares")(e.target.checked)}
              />
              <span>
                Serviços hospitalares (presunção de 8% no IRPJ e 12% na CSLL)
                <span className="block text-xs text-tinta-2">
                  Só vale para quem presta serviços hospitalares e afins na forma da lei; consultório e clínica sem esse enquadramento usam 32%.
                </span>
              </span>
            </label>
          </div>
        </details>
      )}
      {f.atividade === "servico_fator_r" && (
        <details className="rounded-lg border border-borda p-3" open={(f.folha_fator_r_anual ?? 0) > 0} data-testid="bloco-folha-fator-r">
          <summary className="cursor-pointer text-sm font-medium">
            Folha do fator R informada
            <span className="ml-2 text-xs font-normal text-tinta-2">Opcional: use o valor apurado no eSocial ou no PGDAS-D</span>
          </summary>
          <div className="mt-3 flex flex-col gap-3">
            <p className="text-xs text-tinta-2">
              Sem este campo, a folha é calculada: salários + pró-labore + FGTS de 8%. A lei considera as remunerações (com o 13º), o
              pró-labore, o FGTS e a contribuição patronal recolhida fora do DAS, e exclui aluguéis e distribuição de lucros (LC
              123/2006, art. 18, §§ 24 a 26). Informe o valor anual dos últimos 12 meses se ele for diferente do calculado.
            </p>
            <div className="max-w-xs">
              <CampoMoeda id="folha_fator_r" rotulo="Folha anual para o fator R" valor={f.folha_fator_r_anual ?? 0} onChange={set("folha_fator_r_anual")} />
            </div>
          </div>
        </details>
      )}
      {mostrarAnexoIII && f.atividade === "servico_fator_r" && (
        <details className="rounded-lg border border-borda p-3" open={(f.receita_anexo_iii_anual ?? 0) > 0} data-testid="bloco-anexo-iii">
          <summary className="cursor-pointer text-sm font-medium">
            Parte da receita em atividade do Anexo III
            <span className="ml-2 text-xs font-normal text-tinta-2">Opcional: empresa que exerce, de fato, mais de uma atividade</span>
          </summary>
          <div className="mt-3 flex flex-col gap-3">
            <p className="text-xs text-tinta-2">
              Se parte do faturamento vem de um serviço que tributa direto no Anexo III (e a empresa tem o CNAE dele e emite a nota com ele),
              informe aqui o valor anual. Ele é <strong>uma parte</strong> da receita bruta e só muda o Simples Nacional.
            </p>
            <div className="max-w-xs">
              <CampoMoeda id="receita_anexo_iii" rotulo="Receita anual do Anexo III" valor={f.receita_anexo_iii_anual ?? 0} onChange={set("receita_anexo_iii_anual")} />
            </div>
          </div>
        </details>
      )}
      <MensagemErro>{erro}</MensagemErro>
      <div>
        <Botao type="submit" carregando={carregando}>{rotuloBotao}</Botao>
      </div>
    </form>
  );
}
