"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { api, ErroApi } from "@/lib/api";
import { brl, competenciaCurta, numero } from "@/lib/formato";
import type { CompletaEntrada, Financeiro, FinanceiroImportacao, FinanceiroPlanejamento, FinanceiroPrevia } from "@/lib/tipos";

import { Botao, Cartao, MensagemErro, Selecao } from "./ui";

const CAMPOS = ["competencia", "receita", "compras", "folha", "pro_labore", "despesas_creditaveis", "outras_despesas", "receita_exterior", "variacao_cambial"] as const;
const COLUNAS_TABELA: { campo: keyof Financeiro["meses"][number]; rotulo: string }[] = [
  { campo: "receita", rotulo: "Receita" },
  { campo: "compras", rotulo: "Compras" },
  { campo: "folha", rotulo: "Folha" },
  { campo: "pro_labore", rotulo: "Pró-labore" },
  { campo: "despesas_creditaveis", rotulo: "Desp. c/ crédito" },
  { campo: "outras_despesas", rotulo: "Outras desp." },
  { campo: "receita_exterior", rotulo: "Receita exterior" },
  { campo: "variacao_cambial", rotulo: "Var. cambial" },
];

export function paraPlanejamento(p: FinanceiroPlanejamento): Partial<CompletaEntrada> {
  return {
    receita_bruta_anual: p.receita_bruta_anual,
    compras_anual: p.compras_anual,
    folha_clt_anual: p.folha_clt_anual,
    pro_labore_anual: p.pro_labore_anual,
    despesas_creditaveis_anual: p.despesas_creditaveis_anual,
    outras_despesas_anual: p.outras_despesas_anual,
    receita_exterior_anual: p.receita_exterior_anual ?? 0,
    variacao_cambial_anual: p.variacao_cambial_anual ?? 0,
  };
}

/** Receita, folha e despesas por mês vindos de planilha exportada do sistema de contabilidade. */
export function DadosContabeis({
  clienteId,
  onUsarNoPlanejamento,
}: {
  clienteId: number;
  onUsarNoPlanejamento: (p: Partial<CompletaEntrada>, texto: string) => void;
}) {
  const [dados, setDados] = useState<Financeiro | null>(null);
  const [arquivo, setArquivo] = useState<File | null>(null);
  const [previa, setPrevia] = useState<FinanceiroPrevia | null>(null);
  const [mapa, setMapa] = useState<Record<string, number | null>>({});
  const [resultado, setResultado] = useState<FinanceiroImportacao | null>(null);
  const [erro, setErro] = useState("");
  const [ocupado, setOcupado] = useState(false);
  const entrada = useRef<HTMLInputElement>(null);

  const carregar = useCallback(() => {
    api<Financeiro>(`/clientes/${clienteId}/financeiro`).then(setDados).catch(() => setDados(null));
  }, [clienteId]);

  useEffect(() => {
    carregar();
  }, [carregar]);

  async function escolher(f: File) {
    setErro("");
    setResultado(null);
    setPrevia(null);
    const corpo = new FormData();
    corpo.append("arquivos", f);
    setOcupado(true);
    try {
      const p = await api<FinanceiroPrevia>(`/clientes/${clienteId}/financeiro/previa`, { method: "POST", body: corpo });
      setArquivo(f);
      setPrevia(p);
      setMapa(p.sugestao);
    } catch (e) {
      setArquivo(null);
      setErro(e instanceof ErroApi ? e.message : "Não foi possível ler a planilha");
    } finally {
      setOcupado(false);
      if (entrada.current) entrada.current.value = "";
    }
  }

  async function importar() {
    if (!arquivo) return;
    setErro("");
    const corpo = new FormData();
    corpo.append("arquivos", arquivo);
    corpo.append("mapeamento", JSON.stringify(mapa));
    setOcupado(true);
    try {
      setResultado(await api<FinanceiroImportacao>(`/clientes/${clienteId}/financeiro/importar`, { method: "POST", body: corpo }));
      setPrevia(null);
      setArquivo(null);
      carregar();
    } catch (e) {
      setErro(e instanceof ErroApi ? e.message : "Falha na importação");
    } finally {
      setOcupado(false);
    }
  }

  async function apagar() {
    if (!confirm("Apagar os dados contábeis importados deste cliente?")) return;
    await api(`/clientes/${clienteId}/financeiro`, { method: "DELETE" });
    setResultado(null);
    carregar();
  }

  const p = dados?.planejamento ?? null;
  const usadas = new Set(Object.values(mapa).filter((v): v is number => v != null));

  return (
    <Cartao
      titulo="Dados contábeis (planilha)"
      acoes={
        p && (
          <Botao
            variante="secundario"
            onClick={() =>
              onUsarNoPlanejamento(
                paraPlanejamento(p),
                `Valores da planilha de ${competenciaCurta(p.periodo_inicio)} a ${competenciaCurta(p.periodo_fim)}` +
                  (p.anualizado ? ` (${p.meses} ${p.meses === 1 ? "mês" : "meses"}, anualizados pela média)` : "") +
                  ". Confira atividade e alíquotas.",
              )
            }
          >
            Usar no planejamento
          </Botao>
        )
      }
    >
      <div className="flex flex-col gap-3 text-sm">
        <p className="text-tinta-2">
          Sem digitar: exporte do seu sistema contábil uma planilha com uma linha por mês (receita, compras, folha, pró-labore,
          despesas; se houver, a receita do exterior e a variação cambial) em .csv ou .xlsx. Você escolhe qual coluna é qual; reenviar um mês troca só o que a planilha trouxer.{" "}
          <a className="font-medium text-marca underline" href="/api/financeiro/modelo.csv">Baixar planilha modelo</a>
        </p>
        <input
          ref={entrada}
          type="file"
          accept=".csv,.xlsx,.txt"
          aria-label="Planilha de dados contábeis"
          className="hidden"
          onChange={(e) => e.target.files?.[0] && escolher(e.target.files[0])}
        />
        <div>
          <Botao variante="secundario" onClick={() => entrada.current?.click()} carregando={ocupado && !previa}>Escolher planilha</Botao>
        </div>
        <MensagemErro>{erro}</MensagemErro>

        {previa && (
          <div className="flex flex-col gap-3 rounded-lg border border-borda bg-fundo p-3" aria-label="Mapeamento de colunas">
            <div className="font-medium">
              {arquivo?.name}: {previa.total_linhas} {previa.total_linhas === 1 ? "linha" : "linhas"}. Confira o que é cada coluna.
            </div>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {CAMPOS.map((campo) => (
                <Selecao
                  key={campo}
                  rotulo={previa.rotulos[campo] + (campo === "competencia" ? " *" : "")}
                  name={`coluna_${campo}`}
                  value={mapa[campo] ?? ""}
                  onChange={(e) => setMapa((m) => ({ ...m, [campo]: e.target.value === "" ? null : Number(e.target.value) }))}
                >
                  <option value="">Não usar</option>
                  {previa.cabecalhos.map((c, i) => (
                    <option key={i} value={i} disabled={usadas.has(i) && mapa[campo] !== i}>
                      {c || `Coluna ${i + 1}`}
                    </option>
                  ))}
                </Selecao>
              ))}
            </div>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[480px] text-xs">
                <thead>
                  <tr className="border-b border-borda text-tinta-2">
                    {previa.cabecalhos.map((c, i) => (
                      <th key={i} className="px-2 py-1.5 text-left font-medium">{c || `Coluna ${i + 1}`}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {previa.amostra.map((l, n) => (
                    <tr key={n} className="border-b border-borda/70">
                      {l.map((c, i) => (
                        <td key={i} className="px-2 py-1">{c}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="flex flex-wrap gap-2">
              <Botao onClick={importar} carregando={ocupado} disabled={mapa.competencia == null}>Importar dados</Botao>
              <Botao variante="fantasma" onClick={() => { setPrevia(null); setArquivo(null); }}>Cancelar</Botao>
            </div>
          </div>
        )}

        {resultado && (
          <div className="rounded-lg border border-borda bg-fundo p-3">
            <div className="font-medium">
              {resultado.meses_novos} {resultado.meses_novos === 1 ? "mês novo" : "meses novos"} · {resultado.meses_atualizados} atualizados
              {resultado.total_ignoradas > 0 && <> · {resultado.total_ignoradas} linhas ignoradas</>}
            </div>
            {resultado.avisos.map((a) => (
              <p key={a} className="mt-1 text-xs text-tinta-2">{a}</p>
            ))}
            {resultado.ignoradas.length > 0 && (
              <ul className="mt-2 max-h-32 overflow-auto text-xs text-tinta-2">
                {resultado.ignoradas.map((i) => (
                  <li key={i.linha}><span className="font-medium text-tinta">Linha {i.linha}</span>: {i.motivo}</li>
                ))}
              </ul>
            )}
          </div>
        )}

        {dados && dados.meses.length > 0 && (
          <>
            {p && (
              <p className="text-xs text-tinta-2">
                Base do planejamento: {competenciaCurta(p.periodo_inicio)} a {competenciaCurta(p.periodo_fim)} — receita anual {brl(p.receita_bruta_anual)}
                {p.anualizado && <> (média de {p.meses} {p.meses === 1 ? "mês" : "meses"} vezes 12)</>}.
              </p>
            )}
            <div className="overflow-x-auto">
              <table className="num w-full min-w-[640px] text-[13px]">
                <thead>
                  <tr className="border-b border-borda text-xs text-tinta-2">
                    <th className="py-2 pr-2 text-left font-medium">Mês</th>
                    {COLUNAS_TABELA.map((c) => (
                      <th key={c.campo} className="px-2 py-2 text-right font-medium">{c.rotulo}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {[...dados.meses].reverse().map((m) => (
                    <tr key={m.competencia} className="border-b border-borda/70">
                      <td className="py-1.5 pr-2">{competenciaCurta(m.competencia)}</td>
                      {COLUNAS_TABELA.map((c) => {
                        const v = m[c.campo] as number | null;
                        return <td key={c.campo} className="px-2 py-1.5 text-right">{v == null ? "—" : numero(v)}</td>;
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
              <p className="mt-2 text-xs text-tinta-2">Valores em R$. “—” = a planilha não trouxe esse campo.</p>
            </div>
            <div>
              <Botao variante="fantasma" onClick={apagar}>Apagar dados da planilha</Botao>
            </div>
          </>
        )}
      </div>
    </Cartao>
  );
}
