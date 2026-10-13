"use client";

import { useCallback, useEffect, useState } from "react";

import { api, ErroApi, urlProposta } from "@/lib/api";
import type { ResultadoRecuperacao as TResultado, Simulacao } from "@/lib/tipos";

import { ResultadoRecuperacao } from "./ResultadoRecuperacao";
import { Botao, Cartao, MensagemErro } from "./ui";

/** Análise de PIS/Cofins monofásico e ICMS-ST pagos a mais, a partir dos itens das notas importadas. */
export function RecuperacaoImpostos({
  clienteId,
  versao,
  temDocumentos,
  onSalva,
}: {
  clienteId: number;
  versao: number;
  temDocumentos: boolean;
  onSalva: (sim: Simulacao) => void;
}) {
  const [r, setR] = useState<TResultado | null>(null);
  const [salva, setSalva] = useState<Simulacao | null>(null);
  const [salvando, setSalvando] = useState(false);
  const [erro, setErro] = useState("");

  const carregar = useCallback(() => {
    api<TResultado>(`/clientes/${clienteId}/recuperacao`).then(setR).catch(() => setR(null));
  }, [clienteId]);

  useEffect(() => {
    setSalva(null);
    carregar();
  }, [carregar, versao]);

  async function gerar() {
    setErro("");
    setSalvando(true);
    try {
      const sim = await api<Simulacao>(`/clientes/${clienteId}/recuperacao`, { method: "POST", json: {} });
      setSalva(sim);
      onSalva(sim);
    } catch (e) {
      setErro(e instanceof ErroApi ? e.message : "Não foi possível gerar o relatório");
    } finally {
      setSalvando(false);
    }
  }

  if (!r) return null;
  if (!r.disponivel) {
    return (
      <Cartao titulo="Imposto pago a mais no Simples Nacional">
        <p className="text-sm text-tinta-2">
          {temDocumentos
            ? "As notas já importadas ainda não têm os itens. Importe de novo os XML de NF-e de venda (o sistema completa as notas existentes, sem duplicar) para descobrir se o cliente pagou PIS/Cofins ou ICMS a mais em produtos monofásicos e com substituição tributária."
            : "Importe os XML de NF-e de venda para descobrir se o cliente pagou PIS/Cofins ou ICMS a mais em produtos monofásicos e com substituição tributária."}
        </p>
      </Cartao>
    );
  }
  return (
    <section aria-label="Imposto pago a mais no Simples Nacional" className="flex flex-col gap-3">
      <h2 className="text-base font-semibold">Imposto pago a mais no Simples Nacional</h2>
      <MensagemErro>{erro}</MensagemErro>
      <ResultadoRecuperacao
        r={r}
        acoes={
          <>
            <Botao onClick={gerar} carregando={salvando} variante={salva ? "secundario" : "primario"}>
              {salva ? "Gerar novamente" : "Gerar relatório"}
            </Botao>
            {salva && (
              <a href={urlProposta(salva.id)} target="_blank" className="inline-flex h-10 items-center rounded-lg border border-borda px-3 text-sm font-medium hover:bg-fundo">
                Abrir PDF
              </a>
            )}
            {salva && <span className="self-center text-sm text-emerald-700">Relatório salvo em Simulações.</span>}
          </>
        }
      />
    </section>
  );
}
