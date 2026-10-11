"use client";

import { useRouter } from "next/navigation";
import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";

import { api, ErroApi } from "@/lib/api";
import type { Sessao } from "@/lib/tipos";

interface ContextoSessao {
  sessao: Sessao;
  atualizar: (s: Sessao) => void;
  sair: () => Promise<void>;
}

const Contexto = createContext<ContextoSessao | null>(null);

export function useSessao(): ContextoSessao {
  const ctx = useContext(Contexto);
  if (!ctx) throw new Error("useSessao fora do ProvedorSessao");
  return ctx;
}

export function aplicarCorMarca(cor: string) {
  document.documentElement.style.setProperty("--marca", cor);
}

/** Carrega a sessão; sem sessão válida, manda para o login. */
export function ProvedorSessao({ children }: { children: ReactNode }) {
  const router = useRouter();
  const [sessao, setSessao] = useState<Sessao | null>(null);

  useEffect(() => {
    api<Sessao>("/auth/me")
      .then((s) => {
        aplicarCorMarca(s.escritorio.cor_primaria);
        setSessao(s);
      })
      .catch((e) => {
        if (e instanceof ErroApi && e.status === 401) router.replace("/login");
      });
  }, [router]);

  const atualizar = useCallback((s: Sessao) => {
    aplicarCorMarca(s.escritorio.cor_primaria);
    setSessao(s);
  }, []);

  const sair = useCallback(async () => {
    await api("/auth/logout", { method: "POST" });
    router.replace("/login");
  }, [router]);

  if (!sessao) {
    return (
      <div className="grid min-h-screen place-items-center text-sm text-tinta-2" aria-busy>
        Carregando…
      </div>
    );
  }
  return <Contexto.Provider value={{ sessao, atualizar, sair }}>{children}</Contexto.Provider>;
}
