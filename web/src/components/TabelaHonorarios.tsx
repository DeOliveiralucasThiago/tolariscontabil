"use client";

import { useState } from "react";

import { api, ErroApi } from "@/lib/api";
import type { RegimeHonorarios, Sessao } from "@/lib/tipos";

import { CampoMoeda } from "./CampoMoeda";
import { useSessao } from "./Sessao";
import { Botao, Campo, Cartao, MensagemErro, Rotulo, classeCampo } from "./ui";

const REGIMES: [RegimeHonorarios, string][] = [
  ["mei", "MEI"],
  ["simples", "Simples Nacional"],
  ["presumido", "Lucro Presumido"],
  ["real", "Lucro Real"],
];

/** Tabela de honorários do escritório: base de cada regime, adicional por funcionário, adesão e serviços. */
export function TabelaHonorarios() {
  const { sessao, atualizar } = useSessao();
  const admin = sessao.usuario.papel === "admin";
  const atual = sessao.escritorio.honorarios;
  const [base, setBase] = useState<Record<RegimeHonorarios, number>>({
    mei: atual?.base.mei ?? 0,
    simples: atual?.base.simples ?? 0,
    presumido: atual?.base.presumido ?? 0,
    real: atual?.base.real ?? 0,
  });
  const [porFuncionario, setPorFuncionario] = useState(atual?.por_funcionario ?? 0);
  const [adesao, setAdesao] = useState(atual?.adesao ?? 0);
  const [servicos, setServicos] = useState(atual?.servicos ?? "");
  const [validade, setValidade] = useState(atual?.validade_dias ?? 15);
  const [erro, setErro] = useState("");
  const [ok, setOk] = useState("");
  const [salvando, setSalvando] = useState(false);

  async function salvar(e: React.FormEvent) {
    e.preventDefault();
    setErro("");
    setOk("");
    setSalvando(true);
    try {
      const s = await api<Sessao>("/escritorio", {
        method: "PATCH",
        json: { honorarios: { base, por_funcionario: porFuncionario, adesao, servicos, validade_dias: validade } },
      });
      atualizar(s);
      setOk("Tabela de honorários salva.");
    } catch (e) {
      setErro(e instanceof ErroApi ? e.message : "Falha ao salvar a tabela");
    } finally {
      setSalvando(false);
    }
  }

  return (
    <Cartao titulo="Tabela de honorários">
      <p className="mb-4 text-sm text-tinta-2">
        Usada para sugerir o valor da proposta de cada cliente: base do regime recomendado mais o adicional por funcionário.
        Você ajusta o valor antes de enviar.
      </p>
      <form onSubmit={salvar} className="flex flex-col gap-4">
        <fieldset disabled={!admin} className="flex flex-col gap-4 disabled:opacity-70">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {REGIMES.map(([chave, nome]) => (
              <CampoMoeda key={chave} id={`hon-${chave}`} rotulo={`${nome} (por mês)`} valor={base[chave]} onChange={(v) => setBase((b) => ({ ...b, [chave]: v }))} />
            ))}
          </div>
          <div className="grid gap-4 sm:grid-cols-3">
            <CampoMoeda id="hon-funcionario" rotulo="Por funcionário (por mês)" valor={porFuncionario} onChange={setPorFuncionario} />
            <CampoMoeda id="hon-adesao" rotulo="Adesão (pagamento único)" valor={adesao} onChange={setAdesao} />
            <Campo
              rotulo="Validade da proposta (dias)"
              name="hon-validade"
              type="number"
              min={1}
              max={90}
              value={validade}
              onChange={(e) => setValidade(Math.min(90, Math.max(1, Number(e.target.value) || 1)))}
            />
          </div>
          <div>
            <Rotulo htmlFor="hon-servicos">Serviços incluídos (um por linha)</Rotulo>
            <textarea
              id="hon-servicos"
              rows={4}
              maxLength={2000}
              className={`${classeCampo} h-auto py-2`}
              placeholder={"Escrituração fiscal e contábil\nObrigações acessórias\nPlanejamento tributário anual"}
              value={servicos}
              onChange={(e) => setServicos(e.target.value)}
            />
          </div>
        </fieldset>
        <MensagemErro>{erro}</MensagemErro>
        {ok && <p className="text-sm text-emerald-700">{ok}</p>}
        {admin ? (
          <div>
            <Botao type="submit" carregando={salvando}>Salvar tabela</Botao>
          </div>
        ) : (
          <p className="text-xs text-tinta-2">Apenas administradores alteram a tabela.</p>
        )}
      </form>
    </Cartao>
  );
}
