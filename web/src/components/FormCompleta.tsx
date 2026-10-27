"use client";

import { useState } from "react";

import { ATIVIDADES, type Atividade, type CompletaEntrada } from "@/lib/tipos";

import { CampoMoeda, CampoPercentual } from "./CampoMoeda";
import { ConversorDeMoeda } from "./ConversorDeMoeda";
import { SelecaoAtividade } from "./SelecaoAtividade";
import { SeletorProfissao } from "./SeletorProfissao";
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
    receitas_outras_atividades: {},
    folha_so_anexo_iv_pct: 0,
    folha_so_outros_anexos_pct: 0,
    folha_fator_r_anual: null,
    sociedade_profissionais: false,
    profissionais: 0,
    iss_fixo_por_profissional_anual: 0,
    iss_fixo_no_simples: false,
    servicos_hospitalares: false,
    reducao_ibs_cbs: 0,
    ano: 2026,
    ...inicial,
  });
  const [erro, setErro] = useState("");
  const [profissao, setProfissao] = useState("");
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
        const outras = Object.fromEntries(
          Object.entries(f.receitas_outras_atividades ?? {}).filter(([k, v]) => k !== f.atividade && (v ?? 0) > 0),
        ) as CompletaEntrada["receitas_outras_atividades"];
        const somaOutras = Object.values(outras ?? {}).reduce((t, v) => t + (v ?? 0), 0) + (f.receita_anexo_iii_anual ?? 0);
        if ((f.folha_so_anexo_iv_pct ?? 0) + (f.folha_so_outros_anexos_pct ?? 0) > 1) {
          return setErro("As parcelas da folha por atividade somam mais de 100%.");
        }
        if (somaOutras > f.receita_bruta_anual) {
          return setErro("A soma das receitas das outras atividades não pode passar da receita bruta anual (elas são partes dela).");
        }
        onCalcular({
          ...f,
          receitas_outras_atividades: outras,
          folha_fator_r_anual: f.folha_fator_r_anual || null,
          sociedade_profissionais: !mercadoria && !!f.sociedade_profissionais,
          iss_fixo_no_simples: !mercadoria && !!f.sociedade_profissionais && f.atividade === "servico_anexo_iii" && !!f.iss_fixo_no_simples,
          servicos_hospitalares: !mercadoria && !!f.servicos_hospitalares,
          reducao_ibs_cbs: (f.ano ?? 2026) >= 2027 ? f.reducao_ibs_cbs ?? 0 : 0,
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
      <details className="rounded-lg border border-borda p-3" open={(f.ano ?? 2026) >= 2027} data-testid="bloco-ano">
        <summary className="cursor-pointer text-sm font-medium">
          Ano de apuração e Reforma Tributária
          <span className="ml-2 text-xs font-normal text-tinta-2">Padrão: 2026. Escolha 2027 a 2033 para ver CBS e IBS no Presumido e no Real</span>
        </summary>
        <div className="mt-3 flex flex-col gap-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <Selecao
              id="ano_apuracao"
              name="ano_apuracao"
              rotulo="Ano de apuração"
              value={String(f.ano ?? 2026)}
              onChange={(e) => set("ano")(Number(e.target.value))}
              ajuda="O Simples usa a tabela do ano (Res. CGSN 190/2026)."
            >
              {[2026, 2027, 2028, 2029, 2030, 2031, 2032, 2033].map((a) => (
                <option key={a} value={a}>{a}</option>
              ))}
            </Selecao>
            {(f.ano ?? 2026) >= 2027 && (
              <Selecao
                id="reducao_ibs_cbs"
                name="reducao_ibs_cbs"
                rotulo="Redução de alíquota do IBS e da CBS"
                value={String(f.reducao_ibs_cbs ?? 0)}
                onChange={(e) => set("reducao_ibs_cbs")(Number(e.target.value))}
                ajuda="Só vale para o que a lei lista; confirme o enquadramento."
              >
                <option value="0">Nenhuma (alíquota cheia)</option>
                <option value="0.3">30% (profissões regulamentadas listadas)</option>
                <option value="0.6">60% (serviços de saúde listados)</option>
                <option value="1">100% (alíquota zero)</option>
              </Selecao>
            )}
          </div>
          {(f.ano ?? 2026) >= 2027 && (
            <p className="text-xs text-tinta-2">
              Do Lucro Presumido e do Lucro Real, a CBS e o IBS entram no lugar de PIS e Cofins; ICMS e ISS caem de 2029 a 2032 e acabam
              em 2033. As alíquotas de referência ainda são estimativas (CBS 8,8% e IBS 17,7%).
            </p>
          )}
        </div>
      </details>
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
            {f.sociedade_profissionais && (
              <SeletorProfissao
                id="profissao"
                valor={profissao}
                onChange={(p, reducao) => {
                  setProfissao(p);
                  setF((x) => ({ ...x, reducao_ibs_cbs: reducao }));
                }}
              />
            )}
            {f.sociedade_profissionais && (f.ano ?? 2026) < 2027 && (f.reducao_ibs_cbs ?? 0) > 0 && (
              <p className="text-xs text-tinta-2">A redução de IBS e CBS só aparece a partir de 2027: escolha o ano em &ldquo;Ano de apuração e Reforma Tributária&rdquo;.</p>
            )}
            {f.sociedade_profissionais && f.atividade === "servico_anexo_iii" && (
              <label className="flex items-start gap-2 text-sm">
                <input
                  id="iss_fixo_no_simples"
                  type="checkbox"
                  className="mt-1"
                  checked={!!f.iss_fixo_no_simples}
                  onChange={(e) => set("iss_fixo_no_simples")(e.target.checked)}
                />
                <span>
                  Escritório de serviços contábeis: recolhe o ISS fixo ao Município também no Simples
                  <span className="block text-xs text-tinta-2">
                    O DAS deixa de incluir o ISS, que é pago em valor fixo à prefeitura (LC 123, art. 18, § 22-A). Só vale se a lei do município permitir;
                    se não permitir, o ISS vai no DAS pela receita.
                  </span>
                </span>
              </label>
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
      <details
        className="rounded-lg border border-borda p-3"
        open={Object.values(f.receitas_outras_atividades ?? {}).some((v) => (v ?? 0) > 0)}
        data-testid="bloco-atividades-mistas"
      >
        <summary className="cursor-pointer text-sm font-medium">
          Receitas em outras atividades (cada uma no seu Anexo)
          <span className="ml-2 text-xs font-normal text-tinta-2">Opcional: empresa que vende mercadorias e presta serviços, ou tem mais de um tipo de serviço</span>
        </summary>
        <div className="mt-3 flex flex-col gap-3">
          <p className="text-xs text-tinta-2">
            No Simples Nacional cada atividade tributa no Anexo da atividade realmente exercida, com a faixa pela receita total (LC 123/2006, art. 18, § 4º).
            No Lucro Presumido cada uma tem a sua presunção, e o ICMS incide sobre as mercadorias e o ISS sobre os serviços. Informe o valor anual de cada
            atividade <strong>além da principal</strong>; a receita da principal é o que sobra da receita bruta.
          </p>
          <div className="grid gap-4 sm:grid-cols-2">
            {ATIVIDADES.filter((a) => a.valor !== f.atividade && !(f.atividade === "servico_fator_r" && a.valor === "servico_anexo_iii" && mostrarAnexoIII)).map((a) => (
              <CampoMoeda
                key={a.valor}
                id={`outra_${a.valor}`}
                rotulo={`Receita em ${a.rotuloLongo}`}
                valor={f.receitas_outras_atividades?.[a.valor] ?? 0}
                onChange={(v) => setF((x) => ({ ...x, receitas_outras_atividades: { ...x.receitas_outras_atividades, [a.valor]: v } }))}
              />
            ))}
          </div>
          {(f.atividade === "servico_anexo_iv" || (f.receitas_outras_atividades?.servico_anexo_iv ?? 0) > 0) && (
            <div className="flex flex-col gap-3" data-testid="folha-por-atividade">
              <p className="text-xs text-tinta-2">
                Atividade do Anexo IV junto com outra: a CPP patronal fora do DAS incide sobre a folha de quem trabalha só no Anexo IV e, para quem atua nas
                duas atividades, na proporção da receita do Anexo IV (IN RFB 2.110/2022, arts. 168 a 171). Divida a folha: o que sobra é de quem atua nas duas.
                Sem informar, o Tolaris trata todos como atuando nas duas.
              </p>
              <div className="grid gap-4 sm:grid-cols-2">
                <CampoPercentual id="folha_so_iv" rotulo="Folha só do Anexo IV" valor={f.folha_so_anexo_iv_pct ?? 0} onChange={set("folha_so_anexo_iv_pct")} max={100} />
                <CampoPercentual id="folha_so_outros" rotulo="Folha só dos outros Anexos" valor={f.folha_so_outros_anexos_pct ?? 0} onChange={set("folha_so_outros_anexos_pct")} max={100} />
              </div>
            </div>
          )}
        </div>
      </details>
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
