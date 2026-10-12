"use client";

import Link from "next/link";
import type { ComponentProps, ReactNode } from "react";

type Variante = "primario" | "secundario" | "perigo" | "fantasma";

const estilos: Record<Variante, string> = {
  primario: "bg-marca text-white hover:brightness-110 disabled:opacity-60",
  secundario: "bg-superficie text-tinta border border-borda hover:bg-fundo disabled:opacity-60",
  perigo: "bg-superficie text-red-700 border border-red-200 hover:bg-red-50",
  fantasma: "text-tinta-2 hover:text-tinta hover:bg-fundo",
};

const base =
  "inline-flex items-center justify-center gap-2 rounded-lg px-4 h-10 text-sm font-medium transition focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-marca disabled:cursor-not-allowed";

export function Botao({
  variante = "primario",
  carregando,
  className = "",
  children,
  ...props
}: ComponentProps<"button"> & { variante?: Variante; carregando?: boolean }) {
  return (
    <button className={`${base} ${estilos[variante]} ${className}`} disabled={carregando || props.disabled} {...props}>
      {carregando && <Spinner />}
      {children}
    </button>
  );
}

export function BotaoLink({
  variante = "primario",
  className = "",
  ...props
}: ComponentProps<typeof Link> & { variante?: Variante }) {
  return <Link className={`${base} ${estilos[variante]} ${className}`} {...props} />;
}

export function Spinner() {
  return (
    <span
      aria-hidden
      className="inline-block size-4 animate-spin rounded-full border-2 border-current border-r-transparent"
    />
  );
}

export function Cartao({ titulo, acoes, children, className = "" }: {
  titulo?: ReactNode;
  acoes?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`rounded-xl border border-borda bg-superficie p-5 ${className}`}>
      {(titulo || acoes) && (
        <header className="mb-4 flex flex-wrap items-center justify-between gap-2">
          {titulo && <h2 className="text-base font-semibold">{titulo}</h2>}
          {acoes}
        </header>
      )}
      {children}
    </section>
  );
}

export function Rotulo({ children, htmlFor }: { children: ReactNode; htmlFor?: string }) {
  return (
    <label htmlFor={htmlFor} className="mb-1 block text-sm font-medium text-tinta">
      {children}
    </label>
  );
}

export const classeCampo =
  "h-10 w-full rounded-lg border border-borda bg-superficie px-3 text-sm text-tinta placeholder:text-tinta-2/70 focus:border-marca focus:outline-none focus:ring-2 focus:ring-marca/20 disabled:bg-fundo";

export function Campo({
  rotulo,
  ajuda,
  id,
  className = "",
  ...props
}: ComponentProps<"input"> & { rotulo: string; ajuda?: ReactNode }) {
  const campoId = id ?? props.name;
  return (
    <div className={className}>
      <Rotulo htmlFor={campoId}>{rotulo}</Rotulo>
      <input id={campoId} className={classeCampo} {...props} />
      {ajuda && <p className="mt-1 text-xs text-tinta-2">{ajuda}</p>}
    </div>
  );
}

export function Selecao({
  rotulo,
  ajuda,
  id,
  className = "",
  children,
  ...props
}: ComponentProps<"select"> & { rotulo: string; ajuda?: ReactNode }) {
  const campoId = id ?? props.name;
  return (
    <div className={className}>
      <Rotulo htmlFor={campoId}>{rotulo}</Rotulo>
      <select id={campoId} className={classeCampo} {...props}>
        {children}
      </select>
      {ajuda && <p className="mt-1 text-xs text-tinta-2">{ajuda}</p>}
    </div>
  );
}

export function MensagemErro({ children }: { children: ReactNode }) {
  if (!children) return null;
  return (
    <div role="alert" className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">
      {children}
    </div>
  );
}

export function Aviso({ children }: { children: ReactNode }) {
  return (
    <div className="flex gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">
      <span aria-hidden>⚠</span>
      <div>{children}</div>
    </div>
  );
}

const coresEtiqueta: Record<string, string> = {
  prospect: "bg-sky-50 text-sky-800 border-sky-200",
  ativo: "bg-emerald-50 text-emerald-800 border-emerald-200",
  inativo: "bg-zinc-100 text-zinc-700 border-zinc-200",
};

export function Etiqueta({ tom = "inativo", children }: { tom?: string; children: ReactNode }) {
  return (
    <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium ${coresEtiqueta[tom] ?? coresEtiqueta.inativo}`}>
      {children}
    </span>
  );
}

export function Titulo({ children, sub, acoes }: { children: ReactNode; sub?: ReactNode; acoes?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">{children}</h1>
        {sub && <p className="mt-1 text-sm text-tinta-2">{sub}</p>}
      </div>
      {acoes && <div className="flex flex-wrap gap-2">{acoes}</div>}
    </div>
  );
}

export function Abas<T extends string>({
  abas,
  ativa,
  onChange,
}: {
  abas: { id: T; rotulo: string }[];
  ativa: T;
  onChange: (id: T) => void;
}) {
  return (
    <div className="mb-5 flex gap-1 overflow-x-auto border-b border-borda" role="tablist">
      {abas.map((a) => (
        <button
          key={a.id}
          role="tab"
          aria-selected={ativa === a.id}
          onClick={() => onChange(a.id)}
          className={`-mb-px shrink-0 border-b-2 px-4 py-2 text-sm font-medium ${
            ativa === a.id ? "border-marca text-tinta" : "border-transparent text-tinta-2 hover:text-tinta"
          }`}
        >
          {a.rotulo}
        </button>
      ))}
    </div>
  );
}
