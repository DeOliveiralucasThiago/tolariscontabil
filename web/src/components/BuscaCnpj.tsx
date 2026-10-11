"use client";

import { useState } from "react";

import { api, ErroApi } from "@/lib/api";
import { cnpjValido, mascaraCnpj, soDigitos } from "@/lib/formato";
import type { DadosCnpj } from "@/lib/tipos";

import { Botao, Rotulo, classeCampo } from "./ui";

/** Campo de CNPJ com consulta na Receita (via BrasilAPI) para preencher o cadastro. */
export function BuscaCnpj({
  valor,
  onChange,
  onEncontrado,
  id = "cnpj",
}: {
  valor: string;
  onChange: (cnpj: string) => void;
  onEncontrado: (dados: DadosCnpj) => void;
  id?: string;
}) {
  const [buscando, setBuscando] = useState(false);
  const [mensagem, setMensagem] = useState<{ tipo: "erro" | "ok"; texto: string } | null>(null);
  const completo = soDigitos(valor).length === 14;
  const invalido = completo && !cnpjValido(valor);

  async function buscar() {
    setMensagem(null);
    setBuscando(true);
    try {
      const dados = await api<DadosCnpj>(`/cnpj/${soDigitos(valor)}`);
      onEncontrado(dados);
      setMensagem({ tipo: "ok", texto: `${dados.razao_social}${dados.situacao ? ` · ${dados.situacao}` : ""}` });
    } catch (e) {
      setMensagem({ tipo: "erro", texto: e instanceof ErroApi ? e.message : "Falha na consulta" });
    } finally {
      setBuscando(false);
    }
  }

  return (
    <div>
      <Rotulo htmlFor={id}>CNPJ</Rotulo>
      <div className="flex gap-2">
        <input
          id={id}
          inputMode="numeric"
          placeholder="00.000.000/0000-00"
          className={`${classeCampo} num ${invalido ? "border-red-400" : ""}`}
          value={valor}
          aria-invalid={invalido}
          onChange={(e) => {
            setMensagem(null);
            onChange(mascaraCnpj(e.target.value));
          }}
          onKeyDown={(e) => {
            if (e.key === "Enter" && completo && !invalido) {
              e.preventDefault();
              buscar();
            }
          }}
        />
        <Botao type="button" variante="secundario" onClick={buscar} disabled={!completo || invalido} carregando={buscando}>
          Buscar
        </Botao>
      </div>
      {invalido && <p className="mt-1 text-xs text-red-700">CNPJ inválido (dígitos verificadores não conferem).</p>}
      {mensagem && (
        <p className={`mt-1 text-xs ${mensagem.tipo === "erro" ? "text-red-700" : "text-emerald-700"}`}>{mensagem.texto}</p>
      )}
    </div>
  );
}
