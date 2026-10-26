"use client";

import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { BuscaCnae } from "@/components/BuscaCnae";
import { BuscaCnpj } from "@/components/BuscaCnpj";
import { CnaesDaEmpresa } from "@/components/CnaesDaEmpresa";
import { FormCompleta } from "@/components/FormCompleta";
import { ResultadoEnquadramento } from "@/components/ResultadosFase2";
import { SalvarNoCliente } from "@/components/SalvarNoCliente";
import { Cartao, Selecao, Titulo } from "@/components/ui";
import { api } from "@/lib/api";
import { soDigitos } from "@/lib/formato";
import {
  type Atividade,
  type Cliente,
  type CnaesDoCliente,
  type CompletaEntrada,
  type DadosCnpj,
  type ResultadoEnquadramento as TEnquadramento,
} from "@/lib/tipos";
import { useCalculo } from "@/lib/useCalculo";

function PaginaEnquadramento() {
  const params = useSearchParams();
  const clienteDaUrl = params.get("cliente") ? Number(params.get("cliente")) : undefined;
  const calc = useCalculo<CompletaEntrada, TEnquadramento>("enquadramento");
  const [clientes, setClientes] = useState<Cliente[]>([]);
  const [clienteId, setClienteId] = useState<number | "">("");
  const [cnpj, setCnpj] = useState("");
  const [cnaes, setCnaes] = useState<CnaesDoCliente | null>(null);
  const [empresa, setEmpresa] = useState("");
  const [atividade, setAtividade] = useState<Atividade | null>(null);
  const [formKey, setFormKey] = useState(0);

  async function escolherCliente(id: number | "", lista: Cliente[] = clientes) {
    setClienteId(id);
    const c = lista.find((x) => x.id === id);
    if (!c) return;
    setEmpresa(c.razao_social);
    setAtividade(c.atividade);
    setFormKey((k) => k + 1);
    api<CnaesDoCliente>(`/clientes/${c.id}/cnaes`).then(setCnaes).catch(() => setCnaes(null));
  }

  useEffect(() => {
    api<Cliente[]>("/clientes")
      .then((lista) => {
        setClientes(lista);
        if (clienteDaUrl) escolherCliente(clienteDaUrl, lista);
      })
      .catch(() => setClientes([]));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function aoEncontrarCnpj(d: DadosCnpj) {
    setCnaes(d.cnaes_classificados);
    setEmpresa(d.razao_social);
    setAtividade(d.atividade_sugerida);
    setFormKey((k) => k + 1);
    setClienteId(clientes.find((c) => c.cnpj === soDigitos(d.cnpj))?.id ?? "");
  }

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
      <div className="mb-4">
        <Cartao titulo="Empresa">
          <p className="mb-3 text-sm text-tinta-2">
            Escolha um cliente ou digite o CNPJ: o Tolaris traz os CNAEs da Receita (principal e secundários) e a atividade provável.
          </p>
          <div className="grid gap-3 sm:grid-cols-2">
            <Selecao rotulo="Cliente cadastrado" name="enq_cliente" value={clienteId} onChange={(e) => escolherCliente(e.target.value ? Number(e.target.value) : "")}>
              <option value="">Nenhum (usar o CNPJ)</option>
              {clientes.map((c) => (
                <option key={c.id} value={c.id}>{c.razao_social}</option>
              ))}
            </Selecao>
            <BuscaCnpj id="enq_cnpj" valor={cnpj} onChange={setCnpj} onEncontrado={aoEncontrarCnpj} />
          </div>
        </Cartao>
      </div>
      {cnaes && <div className="mb-4"><CnaesDaEmpresa titulo={`CNAEs de ${empresa || "a empresa"}`} dados={cnaes} /></div>}
      <Cartao titulo="Dados da empresa como ela é hoje">
        <FormCompleta
          key={formKey}
          atividadeInicial={atividade ?? "servico_fator_r"}
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
            acoes={<SalvarNoCliente key={String(clienteId)} rota="enquadramento" entrada={calc.entradaUsada} clienteInicial={clienteId || undefined} />}
          />
        </div>
      )}
      <div className="mt-6">
        <BuscaCnae filtroInicial="iii_direto" />
      </div>
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
