"use client";

import { useCallback, useEffect, useState } from "react";

import { api } from "@/lib/api";
import { brl } from "@/lib/formato";
import type { ConferenciaImpedimentos as TConferencia } from "@/lib/tipos";

import { CampoMoeda } from "./CampoMoeda";
import { Botao, Cartao, Etiqueta, MensagemErro } from "./ui";

type Resposta = "" | "sim" | "nao";
const paraResposta = (v: boolean | null): Resposta => (v === true ? "sim" : v === false ? "nao" : "");
const paraApi = (r: Resposta): boolean | null => (r === "sim" ? true : r === "nao" ? false : null);

/** Perguntas dos impedimentos do Simples Nacional (LC 123/2006, art. 3º, § 4º, e art. 17): o contador responde e o Tolaris aplica nas simulações e avisos. */
export function ConferenciaImpedimentos({ clienteId, onSalvo }: { clienteId: number; onSalvo?: () => void }) {
  const [dados, setDados] = useState<TConferencia | null>(null);
  const [respostas, setRespostas] = useState<Record<string, Resposta>>({});
  const [outras, setOutras] = useState(0);
  const [temOutras, setTemOutras] = useState(false);
  const [receita, setReceita] = useState(0);
  const [erro, setErro] = useState("");
  const [salvando, setSalvando] = useState(false);
  const [salvo, setSalvo] = useState(false);

  const aplicar = useCallback((d: TConferencia) => {
    setDados(d);
    setRespostas(Object.fromEntries(d.grupos.flatMap((g) => g.perguntas.map((p) => [p.chave, paraResposta(p.resposta)]))));
    setTemOutras(d.receita_outras_empresas !== null);
    setOutras(d.receita_outras_empresas ?? 0);
  }, []);

  useEffect(() => {
    api<TConferencia>(`/clientes/${clienteId}/impedimentos`).then(aplicar).catch((e) => setErro(e instanceof Error ? e.message : "Falha ao carregar"));
  }, [clienteId, aplicar]);

  async function salvar() {
    setErro("");
    setSalvando(true);
    setSalvo(false);
    try {
      const corpo = {
        respostas: Object.fromEntries(Object.entries(respostas).map(([k, v]) => [k, paraApi(v)])),
        receita_outras_empresas: temOutras ? outras : null,
      };
      const r = await api<TConferencia>(`/clientes/${clienteId}/impedimentos${receita > 0 ? `?receita=${receita}` : ""}`, { method: "PUT", json: corpo });
      aplicar(r);
      setSalvo(true);
      onSalvo?.();
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Falha ao salvar");
    } finally {
      setSalvando(false);
    }
  }

  if (!dados) return <Cartao titulo="Impedimentos ao Simples Nacional"><MensagemErro>{erro}</MensagemErro></Cartao>;
  const veredito =
    dados.simples_possivel === false ? <Etiqueta tom="perigo">Há impedimento ao Simples</Etiqueta>
    : dados.simples_possivel === true ? <Etiqueta tom="ativo">Nenhum impedimento encontrado</Etiqueta>
    : <Etiqueta tom="atencao">Conferência incompleta ({dados.pendentes} por responder)</Etiqueta>;

  return (
    <Cartao titulo="Impedimentos ao Simples Nacional">
      <div className="flex flex-col gap-4" data-testid="conferencia-impedimentos">
        <p className="text-sm text-tinta-2">
          O Tolaris não sabe quem são os sócios, se há débito ou o que a empresa vende. Responda as perguntas da LC 123/2006 (art. 3º, § 4º, e art. 17): um &ldquo;sim&rdquo;
          torna o Simples inaplicável nas simulações do cliente e gera aviso na Central. A natureza jurídica e os CNAEs são conferidos sozinhos.
        </p>
        <div className="flex flex-wrap items-center gap-2" data-testid="veredito-impedimentos">{veredito}</div>
        {dados.automaticos.length > 0 && (
          <ul className="list-disc rounded-lg border border-red-200 bg-red-50 p-3 pl-7 text-sm text-red-900" data-testid="impedimentos-automaticos">
            {dados.automaticos.map((a, i) => (
              <li key={i}><strong>{a.origem}:</strong> {a.texto} <span className="whitespace-nowrap">({a.base_legal})</span></li>
            ))}
          </ul>
        )}
        {dados.achados.length > 0 && (
          <ul className="list-disc rounded-lg border border-amber-200 bg-amber-50 p-3 pl-7 text-sm text-amber-900" data-testid="impedimentos-achados">
            {dados.achados.map((a) => (
              <li key={a.chave}>
                <strong>{a.status === "impede" ? "Impede" : "Depende da receita"}:</strong> {a.texto} <span className="whitespace-nowrap">({a.base_legal})</span>
              </li>
            ))}
          </ul>
        )}
        {dados.grupos.map((g) => (
          <fieldset key={g.grupo} className="flex flex-col gap-2">
            <legend className="mb-1 text-sm font-medium">{g.grupo}</legend>
            {g.perguntas.map((p) => (
              <div key={p.chave} className="grid gap-1 rounded-lg border border-borda p-2.5 sm:grid-cols-[1fr_150px] sm:items-center">
                <div className="text-sm">
                  <label htmlFor={`imp_${p.chave}`}>{p.texto}</label>
                  <span className="ml-1 whitespace-nowrap text-xs text-tinta-2">({p.base_legal})</span>
                  {p.ajuda && <p className="mt-0.5 text-xs text-tinta-2">{p.ajuda}</p>}
                </div>
                <select
                  id={`imp_${p.chave}`}
                  className="h-9 rounded-lg border border-borda bg-superficie px-2 text-sm"
                  value={respostas[p.chave] ?? ""}
                  onChange={(e) => setRespostas((r) => ({ ...r, [p.chave]: e.target.value as Resposta }))}
                >
                  <option value="">Não respondida</option>
                  <option value="nao">Não</option>
                  <option value="sim">Sim</option>
                </select>
              </div>
            ))}
          </fieldset>
        ))}
        <div className="grid gap-3 rounded-lg border border-borda p-3 sm:grid-cols-2">
          <div className="sm:col-span-2 text-sm">
            <strong className="font-medium">Receita global</strong>: três impedimentos (sócio empresário ou de outra empresa; sócio com mais de 10% de outra; sócio administrador de outra) só valem se a
            receita da empresa somada à das outras empresas dos sócios passar de {brl(dados.limite_receita_global)}.
          </div>
          <label className="flex items-center gap-2 text-sm sm:col-span-2">
            <input id="tem_outras" type="checkbox" checked={temOutras} onChange={(e) => setTemOutras(e.target.checked)} />
            Informar a receita bruta anual das outras empresas dos sócios
          </label>
          {temOutras && <CampoMoeda id="receita_outras" rotulo="Receita das outras empresas (ano)" valor={outras} onChange={setOutras} />}
          <CampoMoeda id="receita_desta" rotulo="Receita bruta anual desta empresa (para a comparação)" valor={receita} onChange={setReceita} ajuda="Opcional; as simulações usam a receita de cada uma." />
        </div>
        <MensagemErro>{erro}</MensagemErro>
        {salvo && <p className="text-sm text-emerald-700" role="status">Conferência salva.</p>}
        <div><Botao onClick={salvar} carregando={salvando}>Salvar conferência</Botao></div>
      </div>
    </Cartao>
  );
}
