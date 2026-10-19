"use client";

import { usePathname } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { passosDaPagina, TOUR_GERAL, type Passo } from "@/lib/tour";

import { useSessao } from "./Sessao";
import { TourGuiado } from "./TourGuiado";

const VERSAO = "v1";

function chaveVisto(usuarioId: number) {
  return `tolaris:tour:${VERSAO}:${usuarioId}`;
}

/** Botão "? Ajuda" e o tour de primeiro acesso. O tour geral abre sozinho uma vez por usuário e navegador. */
export function AjudaDoSistema() {
  const { sessao } = useSessao();
  const caminho = usePathname();
  const [passos, setPassos] = useState<Passo[] | null>(null);
  const [menuAberto, setMenuAberto] = useState(false);
  const [geral, setGeral] = useState(false);
  const paginaAtual = passosDaPagina(caminho);

  // Primeiro acesso: abre o tour geral. Navegadores automatizados (testes) só abrem se forçado.
  useEffect(() => {
    try {
      if (localStorage.getItem(chaveVisto(sessao.usuario.id))) return;
      if (navigator.webdriver && !localStorage.getItem("tolaris:tour:forcar")) return;
    } catch {
      return; // armazenamento bloqueado: não insiste com o tour
    }
    const t = setTimeout(() => {
      setPassos(TOUR_GERAL);
      setGeral(true);
    }, 700);
    return () => clearTimeout(t);
  }, [sessao.usuario.id]);

  const terminar = useCallback(
    () => {
      setPassos(null);
      if (geral) {
        try {
          localStorage.setItem(chaveVisto(sessao.usuario.id), "1");
        } catch {
          /* sem armazenamento: o tour volta no próximo acesso */
        }
      }
      setGeral(false);
    },
    [geral, sessao.usuario.id],
  );

  function iniciar(p: Passo[], deTour: boolean) {
    setMenuAberto(false);
    setGeral(deTour);
    setPassos(p);
  }

  return (
    <>
      {!passos && (
        <div className="fixed bottom-4 right-4 z-30 flex flex-col items-end gap-2">
          {menuAberto && (
            <div role="menu" className="w-64 rounded-xl border border-borda bg-superficie p-1.5 text-sm shadow-lg">
              <button role="menuitem" className="block w-full rounded-lg px-3 py-2 text-left hover:bg-fundo" onClick={() => iniciar(TOUR_GERAL, true)}>
                <div className="font-medium">Tour do sistema</div>
                <div className="text-xs text-tinta-2">Para que serve cada menu (1 minuto)</div>
              </button>
              <button
                role="menuitem"
                disabled={!paginaAtual}
                className="block w-full rounded-lg px-3 py-2 text-left hover:bg-fundo disabled:opacity-50"
                onClick={() => paginaAtual && iniciar(paginaAtual, false)}
              >
                <div className="font-medium">Ajuda desta tela</div>
                <div className="text-xs text-tinta-2">{paginaAtual ? "Explica os botões e as áreas desta página" : "Esta tela não tem ajuda guiada"}</div>
              </button>
            </div>
          )}
          <button
            type="button"
            onClick={() => setMenuAberto((v) => !v)}
            aria-expanded={menuAberto}
            aria-haspopup="menu"
            className="flex h-10 items-center gap-2 rounded-full border border-borda bg-superficie px-4 text-sm font-medium shadow-md hover:bg-fundo"
          >
            <span aria-hidden className="grid h-5 w-5 place-items-center rounded-full bg-marca text-xs font-bold text-white">?</span>
            Ajuda
          </button>
        </div>
      )}
      {passos && <TourGuiado passos={passos} onFim={terminar} />}
    </>
  );
}
