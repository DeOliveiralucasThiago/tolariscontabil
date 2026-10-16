"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { api, ErroApi } from "@/lib/api";
import type { CompletarResultado } from "@/lib/tipos";

import { Aviso, Botao, MensagemErro } from "./ui";

/** Completa razão social, CNPJ→CNAE, atividade e regime dos clientes importados só com o CNPJ, em lotes pequenos. */
export function CompletarCadastros({ onProgresso }: { onProgresso?: () => void }) {
  const [pendentes, setPendentes] = useState<number | null>(null);
  const [total, setTotal] = useState(0);
  const [rodando, setRodando] = useState(false);
  const [naoEncontrados, setNaoEncontrados] = useState<CompletarResultado["nao_encontrados"]>([]);
  const [indisponivel, setIndisponivel] = useState(false);
  const [erro, setErro] = useState("");
  const parar = useRef(false);

  const contar = useCallback(() => {
    api<{ pendentes: number }>("/clientes-lote/pendentes")
      .then((r) => setPendentes(r.pendentes))
      .catch(() => setPendentes(null));
  }, []);

  useEffect(() => {
    contar();
  }, [contar]);

  async function completar() {
    setErro("");
    setIndisponivel(false);
    setNaoEncontrados([]);
    parar.current = false;
    setRodando(true);
    setTotal(pendentes ?? 0);
    try {
      for (;;) {
        const r = await api<CompletarResultado>("/clientes-lote/completar", { method: "POST" });
        setPendentes(r.restantes);
        setNaoEncontrados((antes) => [...antes, ...r.nao_encontrados]);
        onProgresso?.();
        if (r.indisponivel) {
          setIndisponivel(true);
          break;
        }
        if (r.restantes === 0 || parar.current || r.completados + r.nao_encontrados.length === 0) break;
      }
    } catch (e) {
      setErro(e instanceof ErroApi ? e.message : "Falha ao completar o cadastro");
    } finally {
      setRodando(false);
      contar();
    }
  }

  if (!pendentes && naoEncontrados.length === 0 && !indisponivel && !erro) return null;
  const feitos = Math.max(0, total - (pendentes ?? 0));
  return (
    <div className="mb-4 flex flex-col gap-3 rounded-lg border border-borda bg-fundo p-3 text-sm" aria-label="Completar cadastros">
      {pendentes ? (
        <div className="flex flex-wrap items-center gap-3">
          <span>
            <strong>{pendentes}</strong> {pendentes === 1 ? "cliente com cadastro por completar" : "clientes com cadastro por completar"}. Buscamos razão
            social, CNAE, atividade e regime pelo CNPJ (só preenchemos o que está vazio).
          </span>
          <Botao variante="secundario" onClick={completar} carregando={rodando}>
            {rodando ? `Completando… ${feitos}/${total}` : "Completar pelo CNPJ"}
          </Botao>
          {rodando && <Botao variante="fantasma" onClick={() => (parar.current = true)}>Pausar</Botao>}
        </div>
      ) : (
        <span className="text-emerald-700">Cadastros completados.</span>
      )}
      {rodando && total > 0 && (
        <div className="h-2 w-full overflow-hidden rounded bg-borda" role="progressbar" aria-valuenow={feitos} aria-valuemax={total}>
          <div className="h-full bg-marca transition-all" style={{ width: `${Math.min(100, (feitos / total) * 100)}%` }} />
        </div>
      )}
      {indisponivel && <Aviso>A consulta de CNPJ está indisponível agora. Os que faltam continuam na fila; tente de novo em alguns minutos.</Aviso>}
      <MensagemErro>{erro}</MensagemErro>
      {naoEncontrados.length > 0 && (
        <div className="text-xs text-tinta-2">
          Não encontrados na Receita (confira o CNPJ e ajuste o cadastro à mão):{" "}
          {naoEncontrados.map((n) => n.cnpj).join(", ")}
        </div>
      )}
    </div>
  );
}
