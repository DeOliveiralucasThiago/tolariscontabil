"use client";

import Link from "next/link";
import { useRef, useState } from "react";

import { CompletarCadastros } from "@/components/CompletarCadastros";
import { Botao, Cartao, MensagemErro, Selecao, Titulo } from "@/components/ui";
import { api, ErroApi } from "@/lib/api";
import type { ClientesAnalise, ClientesImportacao, ClientesPrevia } from "@/lib/tipos";

const CAMPOS = ["cnpj", "razao_social", "nome_fantasia", "atividade", "regime_atual", "status", "contato_nome", "email", "telefone", "observacoes"];
const ROTULO_SITUACAO: Record<string, string> = { invalido: "CNPJ inválido", existente: "Já cadastrado", repetido: "Repetido na planilha" };

export default function ImportarClientes() {
  const [arquivo, setArquivo] = useState<File | null>(null);
  const [previa, setPrevia] = useState<ClientesPrevia | null>(null);
  const [mapa, setMapa] = useState<Record<string, number | null>>({});
  const [statusPadrao, setStatusPadrao] = useState("ativo");
  const [analise, setAnalise] = useState<ClientesAnalise | null>(null);
  const [resultado, setResultado] = useState<ClientesImportacao | null>(null);
  const [erro, setErro] = useState("");
  const [ocupado, setOcupado] = useState(false);
  const entrada = useRef<HTMLInputElement>(null);

  function corpo(extra: Record<string, string> = {}) {
    const f = new FormData();
    if (arquivo) f.append("arquivos", arquivo);
    f.append("mapeamento", JSON.stringify(mapa));
    Object.entries(extra).forEach(([k, v]) => f.append(k, v));
    return f;
  }

  async function escolher(f: File) {
    setErro("");
    setAnalise(null);
    setResultado(null);
    setPrevia(null);
    const c = new FormData();
    c.append("arquivos", f);
    setOcupado(true);
    try {
      const p = await api<ClientesPrevia>("/clientes-lote/previa", { method: "POST", body: c });
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

  async function conferir() {
    setErro("");
    setOcupado(true);
    try {
      setAnalise(await api<ClientesAnalise>("/clientes-lote/analisar", { method: "POST", body: corpo() }));
    } catch (e) {
      setAnalise(null);
      setErro(e instanceof ErroApi ? e.message : "Falha ao conferir a planilha");
    } finally {
      setOcupado(false);
    }
  }

  async function importar() {
    setErro("");
    setOcupado(true);
    try {
      setResultado(await api<ClientesImportacao>("/clientes-lote/importar", { method: "POST", body: corpo({ status_padrao: statusPadrao }) }));
      setPrevia(null);
      setAnalise(null);
      setArquivo(null);
    } catch (e) {
      setErro(e instanceof ErroApi ? e.message : "Falha na importação");
    } finally {
      setOcupado(false);
    }
  }

  const usadas = new Set(Object.values(mapa).filter((v): v is number => v != null));
  return (
    <>
      <Titulo sub="Cadastre a carteira inteira de uma vez, só com o CNPJ de cada cliente." acoes={<Link href="/clientes" className="text-sm text-marca hover:underline">← Clientes</Link>}>
        Importar clientes
      </Titulo>
      <div className="flex flex-col gap-4">
        <Cartao titulo="1. Planilha">
          <div className="flex flex-col gap-3 text-sm">
            <p className="text-tinta-2">
              Envie um .csv ou .xlsx com uma linha por cliente. Só o <strong>CNPJ</strong> é obrigatório; razão social, atividade, regime, e-mail e telefone
              são opcionais. O que faltar é buscado pelo CNPJ na Receita depois.{" "}
              <a className="font-medium text-marca underline" href="/api/clientes-lote/modelo.csv">Baixar planilha modelo</a>
            </p>
            <input
              ref={entrada}
              type="file"
              accept=".csv,.xlsx,.txt"
              aria-label="Planilha de clientes"
              className="hidden"
              onChange={(e) => e.target.files?.[0] && escolher(e.target.files[0])}
            />
            <div>
              <Botao variante="secundario" onClick={() => entrada.current?.click()} carregando={ocupado && !previa}>Escolher planilha</Botao>
            </div>
          </div>
        </Cartao>
        <MensagemErro>{erro}</MensagemErro>

        {previa && (
          <Cartao titulo="2. Confira as colunas">
            <div className="flex flex-col gap-4 text-sm" aria-label="Mapeamento de colunas">
              <div>{arquivo?.name}: {previa.total_linhas} {previa.total_linhas === 1 ? "linha" : "linhas"}.</div>
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {CAMPOS.map((campo) => (
                  <Selecao
                    key={campo}
                    rotulo={previa.rotulos[campo] + (campo === "cnpj" ? " *" : "")}
                    name={`col_${campo}`}
                    value={mapa[campo] ?? ""}
                    onChange={(e) => {
                      setAnalise(null);
                      setMapa((m) => ({ ...m, [campo]: e.target.value === "" ? null : Number(e.target.value) }));
                    }}
                  >
                    <option value="">Não usar</option>
                    {previa.cabecalhos.map((c, i) => (
                      <option key={i} value={i} disabled={usadas.has(i) && mapa[campo] !== i}>{c || `Coluna ${i + 1}`}</option>
                    ))}
                  </Selecao>
                ))}
                <Selecao rotulo="Situação dos clientes sem essa coluna" name="status_padrao" value={statusPadrao} onChange={(e) => setStatusPadrao(e.target.value)}
                  ajuda="Quem já é cliente do escritório: Ativo.">
                  <option value="ativo">Ativo</option>
                  <option value="prospect">Prospect</option>
                  <option value="inativo">Inativo</option>
                </Selecao>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full min-w-[480px] text-xs">
                  <thead>
                    <tr className="border-b border-borda text-tinta-2">
                      {previa.cabecalhos.map((c, i) => <th key={i} className="px-2 py-1.5 text-left font-medium">{c || `Coluna ${i + 1}`}</th>)}
                    </tr>
                  </thead>
                  <tbody>
                    {previa.amostra.map((l, n) => (
                      <tr key={n} className="border-b border-borda/70">{l.map((c, i) => <td key={i} className="px-2 py-1">{c}</td>)}</tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="flex flex-wrap gap-2">
                <Botao onClick={conferir} carregando={ocupado} disabled={mapa.cnpj == null}>Conferir</Botao>
                <Botao variante="fantasma" onClick={() => { setPrevia(null); setArquivo(null); setAnalise(null); }}>Cancelar</Botao>
              </div>
            </div>
          </Cartao>
        )}

        {analise && (
          <Cartao titulo="3. Conferência">
            <div className="flex flex-col gap-3 text-sm" aria-label="Conferência da planilha">
              <div className="font-medium">
                {analise.novos} {analise.novos === 1 ? "cliente novo" : "clientes novos"} · {analise.existentes} já cadastrados · {analise.repetidos} repetidos ·{" "}
                {analise.invalidos} com CNPJ inválido
              </div>
              {analise.avisos.map((a) => <p key={a} className="text-xs text-amber-900">{a}</p>)}
              {analise.problemas.length > 0 && (
                <ul className="max-h-48 overflow-auto text-xs text-tinta-2">
                  {analise.problemas.map((p) => (
                    <li key={p.linha}>
                      <span className="font-medium text-tinta">Linha {p.linha}</span> {p.cnpj && <span className="num">({p.cnpj})</span>}: {ROTULO_SITUACAO[p.situacao] ?? p.motivo}
                    </li>
                  ))}
                  {analise.total_problemas > analise.problemas.length && <li>… e mais {analise.total_problemas - analise.problemas.length}.</li>}
                </ul>
              )}
              <div>
                <Botao onClick={importar} carregando={ocupado} disabled={analise.novos === 0}>
                  Importar {analise.novos} {analise.novos === 1 ? "cliente" : "clientes"}
                </Botao>
              </div>
            </div>
          </Cartao>
        )}

        {resultado && (
          <Cartao titulo="Importação concluída">
            <div className="flex flex-col gap-3 text-sm">
              <div className="font-medium">
                {resultado.criados} {resultado.criados === 1 ? "cliente criado" : "clientes criados"}
                {resultado.pendentes > 0 && <> · {resultado.pendentes} para completar o cadastro</>}
              </div>
              <CompletarCadastros />
              <div>
                <Link href="/clientes" className="font-medium text-marca hover:underline">Ver clientes →</Link>
              </div>
            </div>
          </Cartao>
        )}
      </div>
    </>
  );
}
