import type { Gravidade } from "@/lib/tipos";

const ROTULO: Record<Gravidade, { texto: string; icone: string; classe: string }> = {
  critico: { texto: "Crítico", icone: "▲", classe: "border-red-200 bg-red-50 text-red-800" },
  atencao: { texto: "Atenção", icone: "●", classe: "border-amber-200 bg-amber-50 text-amber-900" },
  oportunidade: { texto: "Oportunidade", icone: "◆", classe: "border-emerald-200 bg-emerald-50 text-emerald-800" },
  info: { texto: "Informação", icone: "○", classe: "border-zinc-200 bg-zinc-100 text-zinc-700" },
};

export const ROTULO_GRAVIDADE: Record<Gravidade, string> = {
  critico: "Crítico",
  atencao: "Atenção",
  oportunidade: "Oportunidade",
  info: "Informação",
};

/** Nível do aviso: sempre ícone e texto, nunca só cor. */
export function ChipGravidade({ gravidade }: { gravidade: Gravidade }) {
  const g = ROTULO[gravidade];
  return (
    <span className={`inline-flex shrink-0 items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium ${g.classe}`}>
      <span aria-hidden>{g.icone}</span>
      {g.texto}
    </span>
  );
}
