"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState, type ReactNode } from "react";

import { useSessao } from "./Sessao";

const MENU = [
  { href: "/painel", rotulo: "Painel", icone: "▦" },
  { href: "/prospeccao", rotulo: "Prospecção", icone: "⚡" },
  { href: "/clientes", rotulo: "Clientes", icone: "☰" },
  { href: "/reforma", rotulo: "Reforma Tributária", icone: "⇄" },
  { href: "/pessoa-fisica", rotulo: "Pessoa física", icone: "◉" },
  { href: "/equipe", rotulo: "Equipe", icone: "☺" },
  { href: "/configuracoes", rotulo: "Configurações", icone: "⚙" },
];

export function Shell({ children }: { children: ReactNode }) {
  const { sessao, sair } = useSessao();
  const caminho = usePathname();
  const [aberto, setAberto] = useState(false);

  const navegacao = (
    <nav className="flex flex-col gap-1">
      {MENU.map((item) => {
        const ativo = caminho === item.href || caminho.startsWith(`${item.href}/`);
        return (
          <Link
            key={item.href}
            href={item.href}
            onClick={() => setAberto(false)}
            aria-current={ativo ? "page" : undefined}
            className={`flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition ${
              ativo ? "bg-marca text-white" : "text-tinta-2 hover:bg-fundo hover:text-tinta"
            }`}
          >
            <span aria-hidden className="w-4 text-center">{item.icone}</span>
            {item.rotulo}
          </Link>
        );
      })}
    </nav>
  );

  const marca = (
    <div className="flex items-center gap-3">
      {sessao.escritorio.tem_logo ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src="/api/escritorio/logo" alt="" className="h-9 w-9 rounded-md object-contain" />
      ) : (
        <div className="grid h-9 w-9 place-items-center rounded-md bg-marca text-sm font-bold text-white">
          {sessao.escritorio.nome.slice(0, 1).toUpperCase()}
        </div>
      )}
      <div className="min-w-0">
        <div className="truncate text-sm font-semibold">{sessao.escritorio.nome}</div>
        <div className="text-xs text-tinta-2">Tolaris Contábil</div>
      </div>
    </div>
  );

  const rodape = (
    <div className="border-t border-borda pt-3 text-sm">
      <div className="truncate font-medium">{sessao.usuario.nome}</div>
      <div className="truncate text-xs text-tinta-2">{sessao.usuario.email}</div>
      <button onClick={sair} className="mt-2 text-xs font-medium text-tinta-2 hover:text-tinta">
        Sair
      </button>
    </div>
  );

  return (
    <div className="min-h-screen lg:grid lg:grid-cols-[240px_minmax(0,1fr)]">
      <aside className="sticky top-0 hidden h-screen flex-col justify-between border-r border-borda bg-superficie p-4 lg:flex">
        <div className="flex flex-col gap-6">
          {marca}
          {navegacao}
        </div>
        {rodape}
      </aside>

      <header className="sticky top-0 z-20 flex items-center justify-between border-b border-borda bg-superficie px-4 py-3 lg:hidden">
        {marca}
        <button
          onClick={() => setAberto((v) => !v)}
          aria-expanded={aberto}
          aria-label="Abrir menu"
          className="rounded-lg border border-borda px-3 py-1.5 text-sm"
        >
          Menu
        </button>
      </header>
      {aberto && (
        <div className="border-b border-borda bg-superficie p-4 lg:hidden">
          {navegacao}
          <div className="mt-4">{rodape}</div>
        </div>
      )}

      <main className="mx-auto w-full max-w-6xl px-4 py-6 sm:px-8 sm:py-8">{children}</main>
    </div>
  );
}
