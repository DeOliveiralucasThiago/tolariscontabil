"use client";

import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";

import { CampoMoeda, CampoPercentual } from "@/components/CampoMoeda";
import { ResultadoAutonomo, ResultadoProLabore, ResultadoSalario } from "@/components/ResultadosFase2";
import { SalvarNoCliente } from "@/components/SalvarNoCliente";
import { SelecaoAtividade } from "@/components/SelecaoAtividade";
import { Abas, Botao, Campo, Cartao, MensagemErro, Selecao, Titulo } from "@/components/ui";
import {
  type Atividade,
  type ResultadoAutonomo as TAutonomo,
  type ResultadoProLabore as TProLabore,
  type ResultadoSalario as TSalario,
} from "@/lib/tipos";
import { useCalculo } from "@/lib/useCalculo";

function Vazio({ texto }: { texto: string }) {
  return (
    <div className="grid min-h-64 place-items-center rounded-xl border border-dashed border-borda bg-superficie p-8 text-center text-sm text-tinta-2">
      {texto}
    </div>
  );
}

function Layout({ formulario, resultado }: { formulario: React.ReactNode; resultado: React.ReactNode }) {
  return <div className="grid grid-cols-1 gap-6 lg:grid-cols-[360px_minmax(0,1fr)]">{formulario}<div>{resultado}</div></div>;
}

function AutonomoXCnpj({ clienteInicial }: { clienteInicial?: number }) {
  const [f, setF] = useState({
    receita_mensal: 0,
    atividade: "servico_fator_r" as Atividade,
    despesas_mensais: 0,
    dependentes: 0,
    iss_fixo_autonomo_mensal: 0,
    aliquota_iss: 0.05,
    mei_permitido: false,
    contabilidade_mensal: 0,
  });
  const set = <K extends keyof typeof f>(k: K) => (v: (typeof f)[K]) => setF((x) => ({ ...x, [k]: v }));
  const calc = useCalculo<typeof f, TAutonomo>("autonomo");
  return (
    <Layout
      formulario={
        <form
          className="flex flex-col gap-4"
          onSubmit={(e) => {
            e.preventDefault();
            if (f.receita_mensal <= 0) return calc.setErro("Informe a receita mensal.");
            calc.calcular(f);
          }}
        >
          <Cartao titulo="Profissional">
            <div className="flex flex-col gap-4">
              <CampoMoeda id="receita_pf" rotulo="Receita mensal" valor={f.receita_mensal} onChange={set("receita_mensal")} obrigatorio />
              <CampoMoeda id="despesas_pf" rotulo="Despesas mensais da atividade" valor={f.despesas_mensais} onChange={set("despesas_mensais")} ajuda="Aluguel de consultório, materiais, etc. (livro-caixa)." />
              <SelecaoAtividade name="atividade_pf" value={f.atividade} onChange={(v) => set("atividade")((v || "servico_fator_r") as Atividade)} />
              <Campo rotulo="Dependentes" name="dependentes_pf" type="number" min={0} max={20} value={f.dependentes} onChange={(e) => set("dependentes")(Number(e.target.value || 0))} />
              <label className="flex items-start gap-2 text-sm">
                <input type="checkbox" checked={f.mei_permitido} onChange={(e) => set("mei_permitido")(e.target.checked)} className="mt-1 accent-[var(--marca)]" />
                <span>A ocupação pode ser MEI <span className="block text-xs text-tinta-2">Profissões intelectuais regulamentadas, em regra, não podem.</span></span>
              </label>
            </div>
          </Cartao>
          <Cartao titulo="Custos de cada opção">
            <div className="flex flex-col gap-4">
              <CampoMoeda id="contab_pf" rotulo="Honorários contábeis (CNPJ)" valor={f.contabilidade_mensal} onChange={set("contabilidade_mensal")} ajuda="Mensalidade para manter a empresa." />
              <CampoMoeda id="iss_fixo" rotulo="ISS do autônomo (por mês)" valor={f.iss_fixo_autonomo_mensal} onChange={set("iss_fixo_autonomo_mensal")} ajuda="Em geral um valor fixo anual da prefeitura, dividido por 12." />
              <CampoPercentual id="iss_pj" rotulo="ISS da empresa" valor={f.aliquota_iss} onChange={set("aliquota_iss")} max={5} />
            </div>
          </Cartao>
          <MensagemErro>{calc.erro}</MensagemErro>
          <Botao type="submit" carregando={calc.calculando} className="h-11">Comparar</Botao>
        </form>
      }
      resultado={
        calc.resultado ? (
          <ResultadoAutonomo r={calc.resultado} acoes={<SalvarNoCliente rota="autonomo" entrada={calc.entradaUsada} clienteInicial={clienteInicial} />} />
        ) : (
          <Vazio texto="Autônomo (carnê-leão), MEI, Simples e Presumido lado a lado: quanto sobra por mês em cada um." />
        )
      }
    />
  );
}

function ProLaboreXDividendos({ clienteInicial }: { clienteInicial?: number }) {
  const [f, setF] = useState({ retirada_mensal: 0, regime: "presumido", pro_labore_otimizado: 0 });
  const set = <K extends keyof typeof f>(k: K) => (v: (typeof f)[K]) => setF((x) => ({ ...x, [k]: v }));
  const calc = useCalculo<Record<string, unknown>, TProLabore>("pro-labore");
  return (
    <Layout
      formulario={
        <form
          className="flex flex-col gap-4"
          onSubmit={(e) => {
            e.preventDefault();
            if (f.retirada_mensal <= 0) return calc.setErro("Informe a retirada mensal.");
            if (f.pro_labore_otimizado > f.retirada_mensal) return calc.setErro("O pró-labore não pode ser maior que a retirada.");
            calc.calcular({ ...f, pro_labore_otimizado: f.pro_labore_otimizado || null });
          }}
        >
          <Cartao titulo="Retirada do sócio">
            <div className="flex flex-col gap-4">
              <CampoMoeda id="retirada" rotulo="Quanto o sócio quer retirar por mês" valor={f.retirada_mensal} onChange={set("retirada_mensal")} obrigatorio />
              <Selecao rotulo="Regime da empresa" name="regime_pl" value={f.regime} onChange={(e) => set("regime")(e.target.value)}>
                <option value="simples">Simples (anexos I, II, III e V)</option>
                <option value="simples_anexo_iv">Simples — Anexo IV</option>
                <option value="presumido">Lucro Presumido</option>
                <option value="real">Lucro Real</option>
              </Selecao>
              <CampoMoeda
                id="pl_otimizado"
                rotulo="Pró-labore na estratégia otimizada"
                valor={f.pro_labore_otimizado}
                onChange={set("pro_labore_otimizado")}
                ajuda="Deixe zerado para usar o salário mínimo."
              />
            </div>
          </Cartao>
          <MensagemErro>{calc.erro}</MensagemErro>
          <Botao type="submit" carregando={calc.calculando} className="h-11">Comparar</Botao>
        </form>
      }
      resultado={
        calc.resultado ? (
          <ResultadoProLabore r={calc.resultado} acoes={<SalvarNoCliente rota="pro-labore" entrada={calc.entradaUsada} clienteInicial={clienteInicial} />} />
        ) : (
          <Vazio texto="Tudo como pró-labore ou pró-labore mínimo + lucros? Com as regras de 2026 (Lei 15.270/2025)." />
        )
      }
    />
  );
}

function SalarioLiquido() {
  const [f, setF] = useState({ salario_bruto: 0, dependentes: 0, pensao_alimenticia: 0 });
  const set = <K extends keyof typeof f>(k: K) => (v: (typeof f)[K]) => setF((x) => ({ ...x, [k]: v }));
  const calc = useCalculo<typeof f, TSalario>("salario-liquido");
  return (
    <Layout
      formulario={
        <form
          className="flex flex-col gap-4"
          onSubmit={(e) => {
            e.preventDefault();
            if (f.salario_bruto <= 0) return calc.setErro("Informe o salário bruto.");
            calc.calcular(f);
          }}
        >
          <Cartao titulo="Empregado CLT">
            <div className="flex flex-col gap-4">
              <CampoMoeda id="bruto" rotulo="Salário bruto" valor={f.salario_bruto} onChange={set("salario_bruto")} obrigatorio />
              <Campo rotulo="Dependentes" name="dependentes_sal" type="number" min={0} max={20} value={f.dependentes} onChange={(e) => set("dependentes")(Number(e.target.value || 0))} />
              <CampoMoeda id="pensao" rotulo="Pensão alimentícia" valor={f.pensao_alimenticia} onChange={set("pensao_alimenticia")} />
            </div>
          </Cartao>
          <MensagemErro>{calc.erro}</MensagemErro>
          <Botao type="submit" carregando={calc.calculando} className="h-11">Calcular</Botao>
        </form>
      }
      resultado={calc.resultado ? <ResultadoSalario r={calc.resultado} /> : <Vazio texto="INSS progressivo e IRRF de 2026, já com a isenção até R$ 5 mil." />}
    />
  );
}

type Aba = "autonomo" | "prolabore" | "salario";

function PaginaPF() {
  const params = useSearchParams();
  const clienteInicial = params.get("cliente") ? Number(params.get("cliente")) : undefined;
  const inicial = (["autonomo", "prolabore", "salario"] as Aba[]).find((a) => a === params.get("aba")) ?? "autonomo";
  const [aba, setAba] = useState<Aba>(inicial);
  return (
    <>
      <Titulo sub="Autônomos, sócios e empregados com as regras de 2026.">Pessoa física</Titulo>
      <Abas
        abas={[
          { id: "autonomo", rotulo: "Vale abrir CNPJ?" },
          { id: "prolabore", rotulo: "Pró-labore × dividendos" },
          { id: "salario", rotulo: "Salário líquido" },
        ]}
        ativa={aba}
        onChange={setAba}
      />
      {aba === "autonomo" && <AutonomoXCnpj clienteInicial={clienteInicial} />}
      {aba === "prolabore" && <ProLaboreXDividendos clienteInicial={clienteInicial} />}
      {aba === "salario" && <SalarioLiquido />}
    </>
  );
}

export default function Pagina() {
  return (
    <Suspense>
      <PaginaPF />
    </Suspense>
  );
}
