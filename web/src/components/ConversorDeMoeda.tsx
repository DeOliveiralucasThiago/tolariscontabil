"use client";

import { useEffect, useState } from "react";

import { api, ErroApi } from "@/lib/api";

import { CampoMoeda } from "./CampoMoeda";
import { Botao, Rotulo, Selecao, classeCampo } from "./ui";

const formatoReais = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });

interface Moeda { codigo: string; nome: string }
interface Ptax { compra: number; venda: number; data_cotacao: string; dia_anterior: boolean; boletim: string }

const taxaTexto = (n: number) => n.toFixed(4).replace(".", ",");
const hoje = () => new Date().toLocaleDateString("sv-SE"); // AAAA-MM-DD

/** Converte um valor em moeda estrangeira para reais pela PTAX do Banco Central (a taxa pode ser trocada à mão). */
export function ConversorDeMoeda({ onUsar }: { onUsar: (reais: number) => void }) {
  const [moedas, setMoedas] = useState<Moeda[]>([{ codigo: "USD", nome: "Dólar dos EUA" }, { codigo: "CAD", nome: "Dólar canadense" }, { codigo: "EUR", nome: "Euro" }]);
  const [moeda, setMoeda] = useState("USD");
  const [valor, setValor] = useState(0);
  const [data, setData] = useState(hoje());
  const [taxa, setTaxa] = useState("");
  const [msg, setMsg] = useState<{ tipo: "ok" | "erro"; texto: string } | null>(null);
  const [buscando, setBuscando] = useState(false);

  useEffect(() => {
    api<Moeda[]>("/cambio/moedas").then(setMoedas).catch(() => undefined);
  }, []);

  const taxaNumero = Number(taxa.replace(",", "."));
  const reais = Number.isFinite(taxaNumero) && taxaNumero > 0 ? Math.round(valor * taxaNumero * 100) / 100 : 0;

  async function buscar() {
    setMsg(null);
    setBuscando(true);
    try {
      const p = await api<Ptax>(`/cambio/ptax?moeda=${moeda}&data=${data}`);
      setTaxa(taxaTexto(p.compra));
      const quando = new Date(`${p.data_cotacao}T12:00:00`).toLocaleDateString("pt-BR");
      setMsg({ tipo: "ok", texto: `PTAX de compra de ${quando}${p.dia_anterior ? " (último dia útil antes da data)" : ""}: ${taxaTexto(p.compra)}. Venda: ${taxaTexto(p.venda)}.` });
    } catch (e) {
      setMsg({ tipo: "erro", texto: e instanceof ErroApi ? e.message : "Falha na consulta; digite a taxa." });
    } finally {
      setBuscando(false);
    }
  }

  return (
    <div className="rounded-lg border border-borda bg-fundo p-3" data-testid="conversor-moeda">
      <p className="mb-3 text-xs text-tinta-2">
        Recebeu em moeda estrangeira? Converta para reais. A taxa vem da PTAX do Banco Central; o contrato de câmbio do
        banco fixa a taxa real da operação, então confira e ajuste se for diferente.
      </p>
      <div className="grid gap-3 sm:grid-cols-2">
        <Selecao rotulo="Moeda recebida" name="moeda_origem" value={moeda} onChange={(e) => setMoeda(e.target.value)}>
          {moedas.map((m) => (
            <option key={m.codigo} value={m.codigo}>{m.codigo} — {m.nome}</option>
          ))}
        </Selecao>
        <CampoMoeda id="valor_moeda" rotulo="Valor na moeda" valor={valor} onChange={setValor} />
        <div>
          <Rotulo htmlFor="data_cambio">Data do câmbio (recebimento)</Rotulo>
          <input id="data_cambio" type="date" max={hoje()} className={classeCampo} value={data} onChange={(e) => setData(e.target.value)} />
        </div>
        <div>
          <Rotulo htmlFor="taxa_cambio">Taxa (R$ por 1 {moeda})</Rotulo>
          <div className="flex gap-2">
            <input id="taxa_cambio" inputMode="decimal" className={`${classeCampo} num text-right`} value={taxa} onChange={(e) => setTaxa(e.target.value.replace(/[^\d,.]/g, ""))} placeholder="0,0000" />
            <Botao type="button" variante="secundario" carregando={buscando} onClick={buscar} disabled={!data}>
              Buscar PTAX
            </Botao>
          </div>
        </div>
      </div>
      {msg && (
        <p role={msg.tipo === "erro" ? "alert" : "status"} className={`mt-2 text-xs ${msg.tipo === "erro" ? "text-red-700" : "text-tinta-2"}`}>{msg.texto}</p>
      )}
      <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
        <span className="text-sm">
          Em reais: <strong className="num" data-testid="reais-convertidos">{formatoReais.format(reais)}</strong>
        </span>
        <Botao type="button" variante="secundario" disabled={reais <= 0} onClick={() => onUsar(reais)}>
          Usar como receita do exterior
        </Botao>
      </div>
    </div>
  );
}
