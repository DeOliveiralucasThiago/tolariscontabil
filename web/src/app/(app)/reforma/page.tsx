"use client";

import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";

import { CampoMoeda, CampoPercentual } from "@/components/CampoMoeda";
import { ResultadoReforma, ResultadoSimplesReforma } from "@/components/ResultadosFase2";
import { SalvarNoCliente } from "@/components/SalvarNoCliente";
import { SelecaoAtividade } from "@/components/SelecaoAtividade";
import { SeletorProfissao } from "@/components/SeletorProfissao";
import { Abas, Botao, Campo, Cartao, MensagemErro, Selecao, Titulo } from "@/components/ui";
import { type Atividade, type ResultadoReforma as TReforma, type ResultadoSimplesReforma as TSimples } from "@/lib/tipos";
import { useCalculo } from "@/lib/useCalculo";

const REDUCOES = [
  { valor: 0, rotulo: "Alíquota padrão" },
  { valor: 0.3, rotulo: "Redução de 30% (profissões regulamentadas)" },
  { valor: 0.6, rotulo: "Redução de 60% (saúde, educação, alimentos…)" },
  { valor: 1, rotulo: "Alíquota zero (cesta básica, medicamentos específicos…)" },
];

function Vazio({ texto }: { texto: string }) {
  return (
    <div className="grid min-h-64 place-items-center rounded-xl border border-dashed border-borda bg-superficie p-8 text-center text-sm text-tinta-2">
      {texto}
    </div>
  );
}

function SelecaoReducao({ valor, onChange, id }: { valor: number; onChange: (v: number) => void; id: string }) {
  return (
    <Selecao rotulo="Regime do setor no IBS/CBS" name={id} id={id} value={valor} onChange={(e) => onChange(Number(e.target.value))}>
      {REDUCOES.map((r) => (
        <option key={r.valor} value={r.valor}>{r.rotulo}</option>
      ))}
    </Selecao>
  );
}

function AliquotasReferencia({
  cbs,
  ibs,
  onCbs,
  onIbs,
}: {
  cbs: number;
  ibs: number;
  onCbs: (v: number) => void;
  onIbs: (v: number) => void;
}) {
  return (
    <details className="rounded-lg border border-borda px-3 py-2 text-sm">
      <summary className="cursor-pointer font-medium">Alíquotas de referência</summary>
      <div className="mt-3 grid grid-cols-2 gap-3">
        <CampoPercentual id="cbs_ref" rotulo="CBS" valor={cbs} onChange={onCbs} max={20} />
        <CampoPercentual id="ibs_ref" rotulo="IBS" valor={ibs} onChange={onIbs} max={30} />
      </div>
      <p className="mt-2 text-xs text-tinta-2">Estimativa oficial de ~26,5%. Atualize quando o Senado fixar a alíquota de 2027.</p>
    </details>
  );
}

function Transicao({ clienteInicial }: { clienteInicial?: number }) {
  const [f, setF] = useState({
    receita_bruta_anual: 0,
    vende_mercadoria: false,
    pis_cofins_nao_cumulativo: false,
    compras_anual: 0,
    despesas_creditaveis_anual: 0,
    aliquota_icms: 0.18,
    aliquota_iss: 0.05,
    aliquota_ipi: 0,
    iss_fixo_anual: 0,
    reducao_setorial: 0,
    cbs_referencia: 0.088,
    ibs_referencia: 0.177,
  });
  const [uni, setUni] = useState({ ativa: false, profissao: "", profissionais: 0, issFixoPorProfissional: 0 });
  const set = <K extends keyof typeof f>(k: K) => (v: (typeof f)[K]) => setF((x) => ({ ...x, [k]: v }));
  const calc = useCalculo<typeof f, TReforma>("reforma");
  const issFixoAnual = f.vende_mercadoria || !uni.ativa ? 0 : uni.profissionais * uni.issFixoPorProfissional;

  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-[360px_minmax(0,1fr)]">
      <form
        className="flex flex-col gap-4"
        onSubmit={(e) => {
          e.preventDefault();
          if (f.receita_bruta_anual <= 0) return calc.setErro("Informe a receita bruta anual.");
          if (!f.vende_mercadoria && uni.ativa && issFixoAnual <= 0) return calc.setErro("Informe a quantidade de profissionais e o ISS fixo anual de cada um.");
          calc.calcular({ ...f, iss_fixo_anual: issFixoAnual });
        }}
      >
        <Cartao titulo="Empresa (Lucro Presumido ou Real)">
          <div className="flex flex-col gap-4">
            <CampoMoeda id="receita_ref" rotulo="Receita bruta anual" valor={f.receita_bruta_anual} onChange={set("receita_bruta_anual")} obrigatorio />
            <Selecao rotulo="Vende" name="vende" value={f.vende_mercadoria ? "m" : "s"} onChange={(e) => set("vende_mercadoria")(e.target.value === "m")}>
              <option value="s">Serviços (ISS)</option>
              <option value="m">Mercadorias (ICMS)</option>
            </Selecao>
            <Selecao
              rotulo="PIS/Cofins hoje"
              name="pis_cofins"
              value={f.pis_cofins_nao_cumulativo ? "nc" : "c"}
              onChange={(e) => set("pis_cofins_nao_cumulativo")(e.target.value === "nc")}
            >
              <option value="c">Cumulativo (Lucro Presumido)</option>
              <option value="nc">Não cumulativo (Lucro Real)</option>
            </Selecao>
            {f.vende_mercadoria ? (
              <div className="grid grid-cols-2 gap-3">
                <CampoPercentual id="icms_ref" rotulo="ICMS" valor={f.aliquota_icms} onChange={set("aliquota_icms")} max={35} />
                <CampoPercentual id="ipi_ref" rotulo="IPI" valor={f.aliquota_ipi} onChange={set("aliquota_ipi")} max={50} />
              </div>
            ) : (
              !uni.ativa && <CampoPercentual id="iss_ref" rotulo="ISS" valor={f.aliquota_iss} onChange={set("aliquota_iss")} max={5} />
            )}
            <SelecaoReducao id="reducao_ref" valor={f.reducao_setorial} onChange={set("reducao_setorial")} />
          </div>
        </Cartao>
        {!f.vende_mercadoria && (
          <Cartao titulo="Sociedade uniprofissional (advocacia, contabilidade, engenharia…)">
            <div className="flex flex-col gap-4" data-testid="bloco-uniprofissional">
              <label className="flex items-start gap-2 text-sm">
                <input
                  id="uni_ativa"
                  type="checkbox"
                  className="mt-1"
                  checked={uni.ativa}
                  onChange={(e) => setUni((u) => ({ ...u, ativa: e.target.checked }))}
                />
                <span>
                  Paga ISS fixo por profissional
                  <span className="block text-xs text-tinta-2">
                    Hoje o ISS é o valor anual de cada profissional (Decreto-Lei 406/1968, art. 9º). A lei da Reforma não traz regra própria para ele: o Tolaris o reduz
                    de 2029 a 2032 como o ISS e o encerra em 2033, quando o decreto-lei é revogado. Depois disso, a sociedade paga IBS e CBS sobre a receita.
                  </span>
                </span>
              </label>
              {uni.ativa && (
                <div className="grid grid-cols-2 gap-3">
                  <Campo
                    id="uni_profissionais"
                    name="uni_profissionais"
                    rotulo="Profissionais"
                    type="number"
                    min={1}
                    step={1}
                    value={uni.profissionais ? String(uni.profissionais) : ""}
                    onChange={(e) => setUni((u) => ({ ...u, profissionais: Math.max(0, Math.floor(Number(e.target.value) || 0)) }))}
                  />
                  <CampoMoeda
                    id="uni_iss_fixo"
                    rotulo="ISS fixo anual de cada um"
                    valor={uni.issFixoPorProfissional}
                    onChange={(v) => setUni((u) => ({ ...u, issFixoPorProfissional: v }))}
                  />
                </div>
              )}
              <SeletorProfissao
                id="uni_profissao"
                valor={uni.profissao}
                onChange={(profissao, reducao) => {
                  setUni((u) => ({ ...u, profissao }));
                  set("reducao_setorial")(reducao);
                }}
              />
            </div>
          </Cartao>
        )}
        <Cartao titulo="Aquisições que geram crédito">
          <div className="flex flex-col gap-4">
            <CampoMoeda
              id="compras_ref"
              rotulo="Compras de mercadorias e insumos (ano)"
              valor={f.compras_anual}
              onChange={set("compras_anual")}
              ajuda="Valor pago hoje, com tributos."
            />
            <CampoMoeda
              id="desp_ref"
              rotulo="Outras aquisições de empresas (ano)"
              valor={f.despesas_creditaveis_anual}
              onChange={set("despesas_creditaveis_anual")}
              ajuda="Energia, aluguel, serviços, software… No modelo novo quase tudo gera crédito."
            />
            <AliquotasReferencia cbs={f.cbs_referencia} ibs={f.ibs_referencia} onCbs={set("cbs_referencia")} onIbs={set("ibs_referencia")} />
          </div>
        </Cartao>
        <MensagemErro>{calc.erro}</MensagemErro>
        <Botao type="submit" carregando={calc.calculando} className="h-11">Simular transição</Botao>
      </form>
      <div>
        {calc.resultado ? (
          <ResultadoReforma r={calc.resultado} acoes={<SalvarNoCliente rota="reforma" entrada={calc.entradaUsada} clienteInicial={clienteInicial} />} />
        ) : (
          <Vazio texto="A carga sobre o consumo de 2025 a 2033, com PIS/Cofins, ICMS/ISS e IPI dando lugar a CBS e IBS." />
        )}
      </div>
    </div>
  );
}

const ANOS_SIMPLES = [2027, 2028, 2029, 2030, 2031, 2032, 2033];

/** Anos do Simples a comparar: cada ano usa a tabela da Res. CGSN 190/2026 (teto de ISS e partilha de IBS/CBS mudam a cada ano). */
function SeletorDeAnos({ anos, onChange }: { anos: number[]; onChange: (a: number[]) => void }) {
  const todos = anos.length === ANOS_SIMPLES.length;
  const alternar = (ano: number) => onChange(ANOS_SIMPLES.filter((a) => (a === ano ? !anos.includes(a) : anos.includes(a))));
  const classe = (ativo: boolean) =>
    `h-8 rounded-lg border px-3 text-xs font-medium ${ativo ? "border-marca bg-marca text-white" : "border-borda text-tinta-2 hover:bg-fundo"}`;
  return (
    <div data-testid="seletor-anos">
      <p className="mb-1 text-sm font-medium">Anos a comparar</p>
      <div className="flex flex-wrap gap-1.5" role="group" aria-label="Anos a comparar">
        {ANOS_SIMPLES.map((a) => (
          <button key={a} type="button" onClick={() => alternar(a)} aria-pressed={anos.includes(a)} className={classe(anos.includes(a))}>
            {a}
          </button>
        ))}
        <button type="button" onClick={() => onChange(todos ? [] : ANOS_SIMPLES)} className={classe(false)}>
          {todos ? "Limpar" : "Todos"}
        </button>
      </div>
      <p className="mt-1 text-xs text-tinta-2">A decisão de agora vale para o primeiro semestre de 2027; os demais anos mostram como a conta muda na transição.</p>
    </div>
  );
}

function SimplesNaReforma({
  clienteInicial,
  receitaInicial,
  atividadeInicial,
}: {
  clienteInicial?: number;
  receitaInicial?: number;
  atividadeInicial?: Atividade;
}) {
  const [f, setF] = useState({
    anos: ANOS_SIMPLES,
    atividade: (atividadeInicial ?? "comercio") as Atividade,
    receita_bruta_anual: receitaInicial ?? 0,
    percentual_b2b: 0.5,
    compras_creditaveis_anual: 0,
    folha_fator_r_anual: 0,
    reducao_setorial: 0,
  });
  const set = <K extends keyof typeof f>(k: K) => (v: (typeof f)[K]) => setF((x) => ({ ...x, [k]: v }));
  const calc = useCalculo<Record<string, unknown>, TSimples>("simples-reforma");
  const entrada = () => ({ ...f, folha_fator_r_anual: f.atividade === "servico_fator_r" ? f.folha_fator_r_anual : null });

  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-[360px_minmax(0,1fr)]">
      <form
        className="flex flex-col gap-4"
        onSubmit={(e) => {
          e.preventDefault();
          if (f.receita_bruta_anual <= 0) return calc.setErro("Informe a receita bruta anual.");
          if (f.receita_bruta_anual > 4_800_000) return calc.setErro("Receita acima do limite do Simples (R$ 4,8 milhões).");
          if (f.anos.length === 0) return calc.setErro("Escolha ao menos um ano para comparar.");
          calc.calcular(entrada());
        }}
      >
        <Cartao titulo="Empresa do Simples Nacional">
          <div className="flex flex-col gap-4">
            <SelecaoAtividade name="atividade_sr" value={f.atividade} onChange={(v) => set("atividade")((v || "servico_fator_r") as Atividade)} />
            <CampoMoeda id="receita_sr" rotulo="Receita bruta anual (RBT12)" valor={f.receita_bruta_anual} onChange={set("receita_bruta_anual")} obrigatorio />
            {f.atividade === "servico_fator_r" && (
              <CampoMoeda
                id="folha_sr"
                rotulo="Folha de 12 meses (fator R)"
                valor={f.folha_fator_r_anual}
                onChange={set("folha_fator_r_anual")}
                ajuda="Salários, pró-labore e FGTS."
              />
            )}
            <div>
              <label htmlFor="b2b" className="mb-1 flex justify-between text-sm font-medium">
                <span>Vendas para empresas (B2B)</span>
                <span className="num">{Math.round(f.percentual_b2b * 100)}%</span>
              </label>
              <input
                id="b2b"
                type="range"
                min={0}
                max={100}
                step={5}
                value={Math.round(f.percentual_b2b * 100)}
                onChange={(e) => set("percentual_b2b")(Number(e.target.value) / 100)}
                className="w-full accent-[var(--marca)]"
              />
              <p className="mt-1 text-xs text-tinta-2">Clientes que compram para revender, produzir ou usar na empresa e tomam crédito.</p>
            </div>
            <CampoMoeda
              id="compras_sr"
              rotulo="Compras de fornecedores do regime regular (ano)"
              valor={f.compras_creditaveis_anual}
              onChange={set("compras_creditaveis_anual")}
              ajuda="Recolhendo por fora, a empresa passa a se creditar do IBS/CBS dessas compras."
            />
            <SelecaoReducao id="reducao_sr" valor={f.reducao_setorial} onChange={set("reducao_setorial")} />
            <SeletorDeAnos anos={f.anos} onChange={set("anos")} />
          </div>
        </Cartao>
        <MensagemErro>{calc.erro}</MensagemErro>
        <Botao type="submit" carregando={calc.calculando} className="h-11">Comparar opções</Botao>
      </form>
      <div>
        {calc.resultado ? (
          <ResultadoSimplesReforma
            r={calc.resultado}
            acoes={<SalvarNoCliente rota="simples-reforma" entrada={calc.entradaUsada} clienteInicial={clienteInicial} />}
          />
        ) : (
          <Vazio texto="A partir de 2027 a empresa do Simples pode recolher IBS/CBS por fora do DAS. Veja quando isso compensa." />
        )}
      </div>
    </div>
  );
}

function PaginaReforma() {
  const params = useSearchParams();
  const clienteInicial = params.get("cliente") ? Number(params.get("cliente")) : undefined;
  const receitaInicial = Number(params.get("receita")) > 0 ? Number(params.get("receita")) : undefined;
  const atividadeInicial = ["comercio", "industria", "servico_anexo_iii", "servico_anexo_iv", "servico_fator_r", "locacao_bens_moveis", "industria_ipi_iss", "transporte_cargas_icms", "transporte_passageiros_icms", "comunicacao_icms"].includes(params.get("atividade") ?? "")
    ? (params.get("atividade") as Atividade)
    : undefined;
  const [aba, setAba] = useState<"transicao" | "simples">(params.get("aba") === "simples" ? "simples" : "transicao");
  return (
    <>
      <Titulo sub="EC 132/2023 e LC 214/2025: transição de 2026 a 2033 e a decisão do Simples sobre IBS/CBS.">
        Reforma Tributária
      </Titulo>
      <Abas
        abas={[
          { id: "transicao", rotulo: "Transição 2025–2033" },
          { id: "simples", rotulo: "Simples: IBS/CBS no DAS ou por fora" },
        ]}
        ativa={aba}
        onChange={setAba}
      />
      {aba === "transicao" ? <Transicao clienteInicial={clienteInicial} /> : <SimplesNaReforma clienteInicial={clienteInicial} receitaInicial={receitaInicial} atividadeInicial={atividadeInicial} />}
    </>
  );
}

export default function Pagina() {
  return (
    <Suspense>
      <PaginaReforma />
    </Suspense>
  );
}
