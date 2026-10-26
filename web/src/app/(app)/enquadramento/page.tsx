"use client";

import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { FormCompleta } from "@/components/FormCompleta";
import { ResultadoEnquadramento } from "@/components/ResultadosFase2";
import { SalvarNoCliente } from "@/components/SalvarNoCliente";
import { Cartao, Titulo } from "@/components/ui";
import { api } from "@/lib/api";
import { type Cliente, type CnaesDoCliente, type CompletaEntrada, type ResultadoEnquadramento as TEnquadramento } from "@/lib/tipos";
import { useCalculo } from "@/lib/useCalculo";

function CnaesDoClienteCartao({ clienteId }: { clienteId: number }) {
  const [dados, setDados] = useState<CnaesDoCliente | null>(null);
  const [cliente, setCliente] = useState<Cliente | null>(null);
  useEffect(() => {
    api<CnaesDoCliente>(`/clientes/${clienteId}/cnaes`).then(setDados).catch(() => setDados(null));
    api<Cliente>(`/clientes/${clienteId}`).then(setCliente).catch(() => setCliente(null));
  }, [clienteId]);
  if (!dados || !dados.cnaes.length) return null;
  return (
    <div data-testid="cnaes-do-cliente">
    <Cartao titulo={`CNAEs de ${cliente?.razao_social ?? "o cliente"}`}>
      <ul className="divide-y divide-borda text-sm">
        {dados.cnaes.map((c) => (
          <li key={c.codigo} className="flex flex-wrap items-baseline justify-between gap-2 py-2">
            <span>
              <span className="num font-medium">{c.codigo.replace(/^(\d{4})(\d)(\d{2})$/, "$1-$2/$3")}</span>{" "}
              {c.principal && <span className="rounded bg-fundo px-1.5 py-0.5 text-xs">principal</span>} {c.descricao}
            </span>
            <span className="text-xs text-tinta-2">{c.anexo}</span>
          </li>
        ))}
      </ul>
      {dados.atividade_fator_r && dados.anexo_iii_no_cadastro.length > 0 && (
        <p className="mt-3 rounded-lg bg-fundo p-3 text-sm" data-testid="candidatos-anexo-iii">
          <strong className="font-medium">Já no cadastro:</strong>{" "}
          {dados.anexo_iii_no_cadastro.map((c) => c.descricao || c.codigo).join("; ")} — {dados.anexo_iii_no_cadastro.length === 1 ? "tende a ser atividade" : "tendem a ser atividades"} do
          Anexo III. Se a empresa realmente presta esse serviço, vale simular abaixo quanto da receita ele representa.
        </p>
      )}
      <p className="mt-3 text-xs text-tinta-2">{dados.aviso} O Tolaris não sugere CNAEs que a empresa ainda não tem: isso exige a tabela oficial e a análise do contador.</p>
    </Cartao>
    </div>
  );
}

function PaginaEnquadramento() {
  const params = useSearchParams();
  const clienteInicial = params.get("cliente") ? Number(params.get("cliente")) : undefined;
  const calc = useCalculo<CompletaEntrada, TEnquadramento>("enquadramento");
  const [percentual, setPercentual] = useState("");
  const p = Number(percentual.replace(",", "."));
  const personalizado = percentual && p > 0 && p <= 100 ? { percentual_anexo_iii: p / 100 } : {};

  return (
    <>
      <Titulo sub="Empresa de serviços no Anexo V do Simples? Veja o que muda no imposto se ela chegar ao Anexo III, e por qual caminho.">
        Enquadramento
      </Titulo>
      <div className="mb-4 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900" role="note">
        <strong className="font-medium">Leia antes de aplicar.</strong> Chegar ao Anexo III só vale na vida real: o pró-labore precisa ser pago de
        verdade, e uma atividade do Anexo III precisa ser exercida de fato, com o CNAE no cadastro e nota fiscal desse serviço. A Receita enquadra
        pela atividade realmente exercida; incluir um CNAE sem a atividade pode ser desconsiderado, com cobrança e multa. Decida com o contador.
      </div>
      {clienteInicial && <div className="mb-4"><CnaesDoClienteCartao clienteId={clienteInicial} /></div>}
      <Cartao titulo="Dados da empresa como ela é hoje">
        <FormCompleta
          atividadeInicial="servico_fator_r"
          onCalcular={(e) => calc.calcular({ ...e, ...personalizado } as CompletaEntrada)}
          carregando={calc.calculando}
          rotuloBotao="Analisar enquadramento"
          mostrarAnexoIII={false}
        />
        <div className="mt-4 max-w-xs">
          <label htmlFor="percentual_iii" className="mb-1 block text-sm font-medium">Cenário próprio (opcional)</label>
          <div className="flex items-center gap-2">
            <input
              id="percentual_iii"
              inputMode="decimal"
              className="h-10 w-24 rounded-lg border border-borda bg-superficie px-3 text-right"
              value={percentual}
              onChange={(e) => setPercentual(e.target.value.replace(/[^\d,.]/g, ""))}
              placeholder="30"
            />
            <span className="text-sm">% da receita em atividade do Anexo III</span>
          </div>
          <p className="mt-1 text-xs text-tinta-2">Além dos cenários de 25%, 50% e 100%.</p>
        </div>
      </Cartao>
      {calc.erro && <p role="alert" className="mt-4 text-sm text-red-700">{calc.erro}</p>}
      {calc.resultado && (
        <div className="mt-6">
          <ResultadoEnquadramento
            r={calc.resultado}
            acoes={<SalvarNoCliente rota="enquadramento" entrada={calc.entradaUsada} clienteInicial={clienteInicial} />}
          />
        </div>
      )}
    </>
  );
}

export default function Pagina() {
  return (
    <Suspense>
      <PaginaEnquadramento />
    </Suspense>
  );
}
