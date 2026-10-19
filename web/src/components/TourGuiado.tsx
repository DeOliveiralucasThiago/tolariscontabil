"use client";

import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";

import type { Passo } from "@/lib/tour";

const LARGURA = 360;
const FOLGA = 8;

interface Retangulo {
  top: number;
  left: number;
  width: number;
  height: number;
}

function visivel(el: Element): boolean {
  const r = el.getBoundingClientRect();
  return r.width > 0 && r.height > 0 && getComputedStyle(el).visibility !== "hidden";
}

/** Primeiro elemento visível que casa com o alvo: seletor CSS ou "texto:Rótulo" (link, botão ou aba). */
function acharAlvo(alvo: string | undefined): HTMLElement | null {
  if (!alvo) return null;
  try {
    if (alvo.startsWith("texto:")) {
      const texto = alvo.slice(6).trim().toLowerCase();
      const candidatos = Array.from(document.querySelectorAll<HTMLElement>("a, button, [role=tab]"));
      return candidatos.find((e) => visivel(e) && (e.textContent ?? "").trim().toLowerCase().includes(texto)) ?? null;
    }
    return Array.from(document.querySelectorAll<HTMLElement>(alvo)).find(visivel) ?? null;
  } catch {
    return null; // seletor inválido: cai no balão central
  }
}

function medir(el: HTMLElement): Retangulo {
  const r = el.getBoundingClientRect();
  return { top: r.top, left: r.left, width: r.width, height: r.height };
}

/** Escolhe onde pôr o balão: à direita do alvo, abaixo ou acima, sempre dentro da tela. */
function posicionar(alvo: Retangulo, altura: number): { top: number; left: number } {
  const vw = window.innerWidth;
  const vh = window.innerHeight;
  const largura = Math.min(LARGURA, vw - 2 * FOLGA * 2);
  const limitarX = (x: number) => Math.max(16, Math.min(x, vw - largura - 16));
  const limitarY = (y: number) => Math.max(16, Math.min(y, vh - altura - 16));
  if (vw - (alvo.left + alvo.width) >= largura + 32) {
    return { top: limitarY(alvo.top + alvo.height / 2 - altura / 2), left: alvo.left + alvo.width + 16 };
  }
  if (vh - (alvo.top + alvo.height) >= altura + 32) return { top: alvo.top + alvo.height + 16, left: limitarX(alvo.left) };
  if (alvo.top >= altura + 32) return { top: alvo.top - altura - 16, left: limitarX(alvo.left) };
  return { top: limitarY(vh / 2 - altura / 2), left: limitarX(vw / 2 - largura / 2) };
}

/** Passo a passo com balão e destaque sobre cada elemento. Sem dependências: o destaque é um recorte de sombra. */
export function TourGuiado({ passos, onFim }: { passos: Passo[]; onFim: (concluido: boolean) => void }) {
  const [indice, setIndice] = useState(0);
  const [alvo, setAlvo] = useState<Retangulo | null>(null);
  const [pos, setPos] = useState<{ top: number; left: number } | null>(null);
  const balao = useRef<HTMLDivElement>(null);
  const elemento = useRef<HTMLElement | null>(null);
  const passo = passos[indice];
  const ultimo = indice === passos.length - 1;

  const reposicionar = useCallback(() => {
    const el = elemento.current;
    const r = el && document.contains(el) ? medir(el) : null;
    setAlvo(r);
    const altura = balao.current?.offsetHeight ?? 200;
    setPos(r ? posicionar(r, altura) : null);
  }, []);

  // Encontra o alvo do passo (abrindo o menu do celular se preciso), rola até ele e mede
  useEffect(() => {
    let cancelado = false;
    let tentativas = 0;
    const procurar = () => {
      if (cancelado) return;
      const el = acharAlvo(passo.alvo);
      if (!el && passo.menu && tentativas === 0) {
        window.dispatchEvent(new CustomEvent("tolaris:menu", { detail: true }));
      }
      if (!el && passo.alvo && tentativas < 5) {
        tentativas += 1;
        setTimeout(procurar, 120); // dá tempo de o menu abrir e da página renderizar
        return;
      }
      elemento.current = el;
      el?.scrollIntoView({ block: "center", behavior: "auto" });
      reposicionar();
      requestAnimationFrame(reposicionar);
    };
    procurar();
    return () => {
      cancelado = true;
    };
  }, [passo, reposicionar]);

  useLayoutEffect(() => {
    reposicionar();
  }, [indice, reposicionar]);

  useEffect(() => {
    const aoMudar = () => reposicionar();
    window.addEventListener("resize", aoMudar);
    window.addEventListener("scroll", aoMudar, true);
    return () => {
      window.removeEventListener("resize", aoMudar);
      window.removeEventListener("scroll", aoMudar, true);
    };
  }, [reposicionar]);

  const fechar = useCallback(
    (concluido: boolean) => {
      window.dispatchEvent(new CustomEvent("tolaris:menu", { detail: false }));
      onFim(concluido);
    },
    [onFim],
  );

  const avancar = useCallback(() => (ultimo ? fechar(true) : setIndice((i) => i + 1)), [ultimo, fechar]);
  const voltar = useCallback(() => setIndice((i) => Math.max(0, i - 1)), []);

  useEffect(() => {
    const tecla = (e: KeyboardEvent) => {
      if (e.key === "Escape") fechar(false);
      else if (e.key === "ArrowRight") avancar();
      else if (e.key === "ArrowLeft") voltar();
    };
    window.addEventListener("keydown", tecla);
    return () => window.removeEventListener("keydown", tecla);
  }, [avancar, voltar, fechar]);

  useEffect(() => {
    balao.current?.querySelector<HTMLButtonElement>("[data-principal]")?.focus();
  }, [indice]);

  const centralizado = !alvo || !pos;
  const estiloBalao = centralizado
    ? { top: "50%", left: "50%", transform: "translate(-50%, -50%)", width: `min(${LARGURA}px, calc(100vw - 32px))` }
    : { top: pos.top, left: pos.left, width: `min(${LARGURA}px, calc(100vw - 32px))` };

  return (
    <div className="fixed inset-0 z-[9998]" role="presentation">
      {/* Bloqueia cliques no fundo enquanto o tour está aberto */}
      <div className="absolute inset-0" style={centralizado ? { background: "rgba(15, 23, 42, 0.55)" } : undefined} />
      {alvo && (
        <div
          aria-hidden
          className="pointer-events-none absolute rounded-lg transition-all duration-150"
          style={{
            top: alvo.top - 6,
            left: alvo.left - 6,
            width: alvo.width + 12,
            height: alvo.height + 12,
            boxShadow: "0 0 0 9999px rgba(15, 23, 42, 0.55), 0 0 0 2px #fff",
          }}
        />
      )}
      <div
        ref={balao}
        role="dialog"
        aria-modal="true"
        aria-labelledby="tour-titulo"
        aria-describedby="tour-texto"
        className="absolute rounded-xl border border-borda bg-superficie p-4 shadow-2xl"
        style={estiloBalao}
      >
        <div className="mb-1 flex items-center justify-between gap-2">
          <h2 id="tour-titulo" className="text-base font-semibold">{passo.titulo}</h2>
          <span className="num shrink-0 text-xs text-tinta-2" aria-label={`Passo ${indice + 1} de ${passos.length}`}>
            {indice + 1} de {passos.length}
          </span>
        </div>
        <p id="tour-texto" className="text-sm leading-relaxed text-tinta-2">{passo.texto}</p>
        <div className="mt-4 flex items-center justify-between gap-2">
          <button type="button" onClick={() => fechar(false)} className="text-xs font-medium text-tinta-2 hover:text-tinta">
            {ultimo ? "Fechar" : "Pular tour"}
          </button>
          <div className="flex gap-2">
            {indice > 0 && (
              <button type="button" onClick={voltar} className="h-9 rounded-lg border border-borda px-3 text-sm font-medium hover:bg-fundo">
                Anterior
              </button>
            )}
            <button type="button" data-principal onClick={avancar} className="h-9 rounded-lg bg-marca px-4 text-sm font-medium text-white">
              {ultimo ? "Concluir" : "Próximo"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
