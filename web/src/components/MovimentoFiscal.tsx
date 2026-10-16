"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { api, ErroApi } from "@/lib/api";
import { brl, brlCurto, competenciaCurta, numero } from "@/lib/formato";
import type { CompletaEntrada, Movimento, ResultadoImportacao, Simulacao } from "@/lib/tipos";

import { Indicadores } from "./Blocos";
import { CaixaDoCliente } from "./CaixaDoCliente";
import { DadosContabeis } from "./DadosContabeis";
import { RecuperacaoImpostos } from "./RecuperacaoImpostos";
import { useSessao } from "./Sessao";
import { Aviso, Botao, Cartao, MensagemErro } from "./ui";

const SERIE_SAIDAS = "#2a78d6";
const SERIE_ENTRADAS = "#eb6834";

const rotuloMes = competenciaCurta;

function GraficoMovimento({ meses }: { meses: Movimento["meses"] }) {
  const dados = meses.slice(-12).map((m) => ({ ...m, mes: rotuloMes(m.competencia) }));
  return (
    <div className="h-64 w-full" role="img" aria-label="Vendas e compras por mês, últimos 12 meses">
      <ResponsiveContainer>
        <BarChart data={dados} margin={{ top: 8, right: 8, bottom: 0, left: 8 }} barCategoryGap="22%" barGap={2}>
          <CartesianGrid vertical={false} stroke="var(--borda)" />
          <XAxis dataKey="mes" tickLine={false} axisLine={{ stroke: "var(--borda)" }} tick={{ fill: "var(--tinta-2)", fontSize: 12 }} />
          <YAxis tickFormatter={(v: number) => brlCurto(v)} tickLine={false} axisLine={false} width={78} tick={{ fill: "var(--tinta-2)", fontSize: 11 }} />
          <Tooltip
            cursor={{ fill: "var(--fundo)" }}
            content={({ active, payload }) => {
              if (!active || !payload?.length) return null;
              const d = payload[0].payload as (typeof dados)[number];
              return (
                <div className="rounded-lg border border-borda bg-superficie px-3 py-2 text-xs shadow-sm">
                  <div className="font-semibold">{d.mes}</div>
                  <div className="num">Vendas: {brl(d.saidas)}</div>
                  <div className="num">Compras: {brl(d.entradas)}</div>
                  <div className="num text-tinta-2">{d.documentos} documentos</div>
                </div>
              );
            }}
          />
          <Legend verticalAlign="top" align="left" height={30} iconType="square" wrapperStyle={{ fontSize: 12 }}
            formatter={(v: string) => <span style={{ color: "var(--tinta)" }}>{v}</span>} />
          <Bar dataKey="saidas" name="Vendas (saídas)" fill={SERIE_SAIDAS} radius={[4, 4, 0, 0]} isAnimationActive={false} />
          <Bar dataKey="entradas" name="Compras (entradas)" fill={SERIE_ENTRADAS} radius={[4, 4, 0, 0]} isAnimationActive={false} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

/** Importação de NF-e/SPED e o movimento mensal do cliente. */
export function MovimentoFiscal({
  clienteId,
  temCnpj,
  cliente,
  onUsarNoPlanejamento,
  onRecuperacaoSalva,
  onUsarPlanilha,
}: {
  clienteId: number;
  temCnpj: boolean;
  cliente: { email: string | null; telefone: string | null; contato_nome: string | null; razao_social: string };
  onUsarNoPlanejamento: (receitaAnual: number, comprasAnual: number) => void;
  onRecuperacaoSalva: (sim: Simulacao) => void;
  onUsarPlanilha: (p: Partial<CompletaEntrada>, texto: string) => void;
}) {
  const [mov, setMov] = useState<Movimento | null>(null);
  const [resultado, setResultado] = useState<ResultadoImportacao | null>(null);
  const [erro, setErro] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [versao, setVersao] = useState(0);
  const entrada = useRef<HTMLInputElement>(null);
  const { sessao } = useSessao();

  const carregar = useCallback(() => {
    api<Movimento>(`/clientes/${clienteId}/movimento`).then(setMov).catch(() => setMov(null));
  }, [clienteId]);

  useEffect(() => {
    carregar();
  }, [carregar]);

  async function importar(arquivos: FileList) {
    setErro("");
    setResultado(null);
    const dados = new FormData();
    Array.from(arquivos).forEach((f) => dados.append("arquivos", f));
    setEnviando(true);
    try {
      setResultado(await api<ResultadoImportacao>(`/clientes/${clienteId}/importacoes`, { method: "POST", body: dados }));
      carregar();
      setVersao((v) => v + 1);
    } catch (e) {
      setErro(e instanceof ErroApi ? e.message : "Falha na importação");
    } finally {
      setEnviando(false);
      if (entrada.current) entrada.current.value = "";
    }
  }

  async function apagarTudo() {
    if (!confirm("Apagar todos os documentos importados deste cliente?")) return;
    await api(`/clientes/${clienteId}/documentos`, { method: "DELETE" });
    setResultado(null);
    carregar();
    setVersao((v) => v + 1);
  }

  // Menos de 12 meses importados: anualiza pela média mensal
  const fator = mov && mov.meses_12m > 0 ? 12 / mov.meses_12m : 1;

  return (
    <div className="flex flex-col gap-4">
      <Cartao titulo="Importar documentos fiscais">
        {!temCnpj ? (
          <Aviso>Cadastre o CNPJ do cliente (aba Dados cadastrais) para importar: é por ele que separamos vendas de compras.</Aviso>
        ) : (
          <div className="flex flex-col gap-3 text-sm">
            <p className="text-tinta-2">
              Envie XML de NF-e/NFC-e (soltos ou em .zip) ou o arquivo .txt do SPED Fiscal (EFD ICMS/IPI). Notas repetidas são
              ignoradas, inclusive se vierem no XML e no SPED.
            </p>
            <input
              ref={entrada}
              type="file"
              multiple
              accept=".xml,.zip,.txt"
              aria-label="Arquivos fiscais"
              className="hidden"
              onChange={(e) => e.target.files?.length && importar(e.target.files)}
            />
            <div>
              <Botao onClick={() => entrada.current?.click()} carregando={enviando}>Escolher arquivos</Botao>
            </div>
            <MensagemErro>{erro}</MensagemErro>
            {resultado && (
              <div className="rounded-lg border border-borda bg-fundo p-3">
                <div className="font-medium">
                  {resultado.importados} importados · {resultado.duplicados} já existiam · {resultado.total_ignorados} ignorados
                  {resultado.atualizados > 0 && <> · {resultado.atualizados} completadas com itens</>}
                </div>
                {resultado.ignorados.length > 0 && (
                  <ul className="mt-2 max-h-40 overflow-auto text-xs text-tinta-2">
                    {resultado.ignorados.map((i, n) => (
                      <li key={n}><span className="font-medium text-tinta">{i.arquivo}</span>: {i.motivo}</li>
                    ))}
                  </ul>
                )}
              </div>
            )}
          </div>
        )}
      </Cartao>

      {temCnpj && (
        <CaixaDoCliente
          clienteId={clienteId}
          emailCliente={cliente.email}
          telefoneCliente={cliente.telefone}
          contatoCliente={cliente.contato_nome}
          razaoSocial={cliente.razao_social}
          escritorioNome={sessao.escritorio.nome}
          versao={versao}
          onNovasNotas={() => {
            carregar();
            setVersao((v) => v + 1);
          }}
        />
      )}

      <DadosContabeis clienteId={clienteId} onUsarNoPlanejamento={onUsarPlanilha} />

      {temCnpj && (
        <RecuperacaoImpostos clienteId={clienteId} versao={versao} temDocumentos={Boolean(mov && mov.documentos > 0)} onSalva={onRecuperacaoSalva} />
      )}

      {mov && mov.meses.length > 0 && (
        <>
          <Indicadores
            itens={[
              { rotulo: `Vendas (últimos ${mov.meses_12m} meses)`, valor: brl(mov.receita_12m) },
              { rotulo: `Compras (últimos ${mov.meses_12m} meses)`, valor: brl(mov.compras_12m) },
              { rotulo: "Documentos importados", valor: String(mov.documentos) },
            ]}
          />
          <Cartao
            titulo="Movimento mensal"
            acoes={
              <div className="flex flex-wrap gap-2">
                <Botao variante="secundario" onClick={() => onUsarNoPlanejamento(mov.receita_12m * fator, mov.compras_12m * fator)}>
                  Usar no planejamento
                </Botao>
                <Botao variante="fantasma" onClick={apagarTudo}>Apagar importações</Botao>
              </div>
            }
          >
            {mov.meses_12m < 12 && (
              <p className="mb-2 text-xs text-tinta-2">
                Há {mov.meses_12m} {mov.meses_12m === 1 ? "mês" : "meses"} importados; no planejamento os valores são anualizados pela média mensal.
              </p>
            )}
            <GraficoMovimento meses={mov.meses} />
            <div className="mt-4 overflow-x-auto">
              <table className="num w-full min-w-[640px] text-[13px]">
                <thead>
                  <tr className="border-b border-borda text-xs text-tinta-2">
                    <th className="py-2 pr-2 text-left font-medium">Mês</th>
                    {["Vendas", "Compras", "ICMS", "IPI", "PIS", "Cofins", "Docs."].map((c) => (
                      <th key={c} className="px-2 py-2 text-right font-medium">{c}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {[...mov.meses].reverse().map((m) => (
                    <tr key={m.competencia} className="border-b border-borda/70">
                      <td className="py-1.5 pr-2">{rotuloMes(m.competencia)}</td>
                      <td className="px-2 py-1.5 text-right">{numero(m.saidas)}</td>
                      <td className="px-2 py-1.5 text-right">{numero(m.entradas)}</td>
                      <td className="px-2 py-1.5 text-right">{numero(m.icms)}</td>
                      <td className="px-2 py-1.5 text-right">{numero(m.ipi)}</td>
                      <td className="px-2 py-1.5 text-right">{numero(m.pis)}</td>
                      <td className="px-2 py-1.5 text-right">{numero(m.cofins)}</td>
                      <td className="px-2 py-1.5 text-right">{m.documentos}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p className="mt-2 text-xs text-tinta-2">Valores em R$. Tributos destacados nas notas de venda.</p>
            </div>
          </Cartao>
        </>
      )}
    </div>
  );
}
