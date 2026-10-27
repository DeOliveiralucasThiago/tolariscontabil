"use client";

import Link from "next/link";
import { useState } from "react";

import { BuscaCnpj } from "@/components/BuscaCnpj";
import { CampoMoeda } from "@/components/CampoMoeda";
import { ResultadoComparativo } from "@/components/ResultadoComparativo";
import { SelecaoAtividade } from "@/components/SelecaoAtividade";
import { SeletorNatureza } from "@/components/SeletorNatureza";
import { Botao, Campo, Cartao, MensagemErro, Selecao, Titulo } from "@/components/ui";
import { api, ErroApi, urlProposta } from "@/lib/api";
import { cnpjValido, soDigitos } from "@/lib/formato";
import { type Atividade, type Cliente, type ClienteForm, type Comparativo, type DadosCnpj, type Simulacao } from "@/lib/tipos";

export default function Prospeccao() {
  const [cnpj, setCnpj] = useState("");
  const [cliente, setCliente] = useState<ClienteForm>({ razao_social: "" });
  const [justificativa, setJustificativa] = useState("");
  const [atividade, setAtividade] = useState<Atividade | "">("");
  const [faturamento, setFaturamento] = useState(0);
  const [folha, setFolha] = useState(0);
  const [proLabore, setProLabore] = useState(0);
  const [exterior, setExterior] = useState(0);
  const [ano, setAno] = useState(2026);
  const [resultado, setResultado] = useState<Comparativo | null>(null);
  const [salvo, setSalvo] = useState<{ cliente: Cliente; simulacao: Simulacao } | null>(null);
  const [erro, setErro] = useState("");
  const [calculando, setCalculando] = useState(false);
  const [salvando, setSalvando] = useState(false);

  const entrada = () => ({
    faturamento_mensal: faturamento,
    folha_mensal: folha,
    pro_labore_mensal: proLabore,
    atividade: atividade as Atividade,
    ...(exterior > 0 ? { receita_exterior_mensal: exterior } : {}),
    ...(ano !== 2026 ? { ano } : {}),
    ...(cliente.natureza_juridica ? { natureza_juridica: cliente.natureza_juridica } : {}),
  });

  function preencher(d: DadosCnpj) {
    setCliente({
      razao_social: d.razao_social,
      nome_fantasia: d.nome_fantasia,
      cnae_principal: d.cnae_principal,
      cnae_descricao: d.cnae_descricao,
      cnaes_secundarios: d.cnaes_secundarios,
      natureza_juridica: d.natureza_juridica,
      natureza_juridica_codigo: d.natureza_juridica_codigo,
      municipio: d.municipio,
      uf: d.uf,
      email: d.email,
      telefone: d.telefone,
      regime_atual: d.regime_sugerido,
    });
    if (d.atividade_sugerida) setAtividade(d.atividade_sugerida);
    setJustificativa(d.cnae_descricao ? `CNAE ${d.cnae_principal} — ${d.cnae_descricao}. ${d.atividade_justificativa}` : d.atividade_justificativa);
  }

  async function simular(e: React.FormEvent) {
    e.preventDefault();
    setErro("");
    setSalvo(null);
    if (!atividade) return setErro("Escolha a atividade principal.");
    if (faturamento <= 0) return setErro("Informe o faturamento mensal.");
    if (exterior > faturamento) return setErro("A parte do faturamento vinda do exterior não pode passar do faturamento mensal.");
    setCalculando(true);
    try {
      setResultado(await api<Comparativo>("/simulacoes/previa/expressa", { method: "POST", json: entrada() }));
    } catch (e) {
      setErro(e instanceof ErroApi ? e.message : "Falha no cálculo");
    } finally {
      setCalculando(false);
    }
  }

  async function salvar() {
    setErro("");
    if (cliente.razao_social.trim().length < 2) return setErro("Informe o nome da empresa para salvar o prospect.");
    if (cnpj && !cnpjValido(cnpj)) return setErro("CNPJ inválido.");
    setSalvando(true);
    try {
      const r = await api<{ cliente: Cliente; simulacao: Simulacao }>("/prospeccao", {
        method: "POST",
        json: {
          cliente: { ...cliente, cnpj: cnpj ? soDigitos(cnpj) : null, atividade },
          simulacao: entrada(),
        },
      });
      setSalvo(r);
    } catch (e) {
      setErro(e instanceof ErroApi ? e.message : "Falha ao salvar");
    } finally {
      setSalvando(false);
    }
  }

  return (
    <>
      <Titulo sub="Faturamento, folha e atividade bastam para uma previsão. Busque o CNPJ para preencher o resto.">
        Prospecção rápida
      </Titulo>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[380px_minmax(0,1fr)]">
        <form onSubmit={simular} className="flex flex-col gap-4">
          <Cartao titulo="Empresa">
            <div className="flex flex-col gap-4">
              <BuscaCnpj valor={cnpj} onChange={setCnpj} onEncontrado={preencher} />
              <Campo
                rotulo="Nome da empresa"
                name="razao_social"
                placeholder="Razão social ou nome do prospect"
                value={cliente.razao_social}
                onChange={(e) => setCliente((c) => ({ ...c, razao_social: e.target.value }))}
              />
              <SelecaoAtividade
                rotulo="Atividade principal"
                name="atividade"
                value={atividade}
                onChange={setAtividade}
                vazio="Selecione…"
                ajuda={justificativa || undefined}
              />
              <SeletorNatureza
                id="natureza_prospeccao"
                valor={cliente.natureza_juridica ?? ""}
                onChange={(d) => setCliente((c) => ({ ...c, natureza_juridica: d || null, natureza_juridica_codigo: null }))}
              />
            </div>
          </Cartao>

          <Cartao titulo="Números do mês">
            <div className="flex flex-col gap-4">
              <CampoMoeda id="faturamento" rotulo="Faturamento mensal" valor={faturamento} onChange={setFaturamento} obrigatorio />
              <CampoMoeda id="folha" rotulo="Folha de salários (CLT)" valor={folha} onChange={setFolha} ajuda="Salários brutos dos empregados (com 13º e férias), sem encargos." />
              <CampoMoeda id="prolabore" rotulo="Pró-labore dos sócios" valor={proLabore} onChange={setProLabore} />
              <CampoMoeda
                id="exterior_mensal"
                rotulo="Parte do faturamento vinda do exterior"
                valor={exterior}
                onChange={setExterior}
                ajuda="Opcional: exportação de serviços ou mercadorias, em reais. Fica sem ISS/ICMS e PIS/Cofins (CBS/IBS em 2027+)."
              />
              <Selecao
                id="ano_previa"
                name="ano_previa"
                rotulo="Ano de apuração"
                value={String(ano)}
                onChange={(e) => setAno(Number(e.target.value))}
                ajuda="Padrão 2026. De 2027 a 2033, o Presumido e o Real pagam CBS e IBS no lugar de PIS e Cofins."
              >
                {[2026, 2027, 2028, 2029, 2030, 2031, 2032, 2033].map((a) => (
                  <option key={a} value={a}>{a}</option>
                ))}
              </Selecao>
            </div>
          </Cartao>

          <MensagemErro>{erro}</MensagemErro>
          <Botao type="submit" carregando={calculando} className="h-11">
            Calcular previsão
          </Botao>
        </form>

        <div>
          {resultado ? (
            <ResultadoComparativo
              resultado={resultado}
              acoes={
                salvo ? (
                  <>
                    <a href={urlProposta(salvo.simulacao.id)} target="_blank" className="inline-flex h-10 items-center rounded-lg bg-marca px-4 text-sm font-medium text-white">
                      Abrir proposta em PDF
                    </a>
                    <Link href={`/clientes/${salvo.cliente.id}`} className="inline-flex h-10 items-center rounded-lg border border-borda px-4 text-sm font-medium">
                      Ver cliente
                    </Link>
                  </>
                ) : (
                  <Botao onClick={salvar} carregando={salvando}>
                    Salvar prospect e gerar proposta
                  </Botao>
                )
              }
            />
          ) : (
            <div className="grid h-full min-h-64 place-items-center rounded-xl border border-dashed border-borda bg-superficie p-8 text-center text-sm text-tinta-2">
              <div>
                <div className="text-base font-medium text-tinta">O comparativo aparece aqui</div>
                Simples Nacional, Lucro Presumido e Lucro Real lado a lado, com a memória de cálculo.
              </div>
            </div>
          )}
        </div>
      </div>
    </>
  );
}
