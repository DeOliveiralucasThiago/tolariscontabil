"use client";

import { useState } from "react";

import { api, ErroApi } from "./api";

/** Estado de uma calculadora: envia a entrada para /calculadoras/<rota> e guarda o resultado. */
export function useCalculo<E, R>(rota: string) {
  const [resultado, setResultado] = useState<R | null>(null);
  const [entradaUsada, setEntradaUsada] = useState<E | null>(null);
  const [erro, setErro] = useState("");
  const [calculando, setCalculando] = useState(false);

  async function calcular(entrada: E) {
    setErro("");
    setCalculando(true);
    try {
      setResultado(await api<R>(`/calculadoras/${rota}`, { method: "POST", json: entrada }));
      setEntradaUsada(entrada);
    } catch (e) {
      setErro(e instanceof ErroApi ? e.message : "Falha no cálculo");
    } finally {
      setCalculando(false);
    }
  }

  return { resultado, entradaUsada, erro, setErro, calculando, calcular };
}
