"use client";

import { Rotulo, classeCampo } from "./ui";

const formatador = new Intl.NumberFormat("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

/** Campo em reais: o usuário digita só números e a máscara posiciona os centavos. */
export function CampoMoeda({
  rotulo,
  valor,
  onChange,
  ajuda,
  id,
  obrigatorio,
  prefixo = "R$",
}: {
  rotulo: string;
  valor: number;
  onChange: (v: number) => void;
  ajuda?: string;
  id: string;
  obrigatorio?: boolean;
  /** Símbolo à esquerda do valor; "R$" por padrão (o conversor usa o código da moeda estrangeira). */
  prefixo?: string;
}) {
  return (
    <div>
      <Rotulo htmlFor={id}>{rotulo}</Rotulo>
      <div className="relative">
        <span className="pointer-events-none absolute inset-y-0 left-3 flex items-center text-sm text-tinta-2">{prefixo}</span>
        <input
          id={id}
          inputMode="numeric"
          required={obrigatorio}
          className={`${classeCampo} num pl-12 text-right`}
          value={formatador.format(valor)}
          onChange={(e) => {
            const digitos = e.target.value.replace(/\D/g, "").slice(0, 15);
            onChange(Number(digitos || "0") / 100);
          }}
          onFocus={(e) => e.target.select()}
        />
      </div>
      {ajuda && <p className="mt-1 text-xs text-tinta-2">{ajuda}</p>}
    </div>
  );
}

/** Percentual digitado como número (ex.: 5 = 5%), guardado como fração (0,05). */
export function CampoPercentual({
  rotulo,
  valor,
  onChange,
  id,
  ajuda,
  max = 100,
}: {
  rotulo: string;
  valor: number;
  onChange: (v: number) => void;
  id: string;
  ajuda?: string;
  max?: number;
}) {
  return (
    <div>
      <Rotulo htmlFor={id}>{rotulo}</Rotulo>
      <div className="relative">
        <input
          id={id}
          type="number"
          min={0}
          max={max}
          step="0.01"
          className={`${classeCampo} num pr-8 text-right`}
          value={Number((valor * 100).toFixed(4))}
          onChange={(e) => onChange(Number(e.target.value || 0) / 100)}
        />
        <span className="pointer-events-none absolute inset-y-0 right-3 flex items-center text-sm text-tinta-2">%</span>
      </div>
      {ajuda && <p className="mt-1 text-xs text-tinta-2">{ajuda}</p>}
    </div>
  );
}
