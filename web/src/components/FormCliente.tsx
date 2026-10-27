"use client";

import { useState } from "react";

import { cnpjValido, mascaraCnpj, soDigitos } from "@/lib/formato";
import {
  ROTULO_REGIME,
  ROTULO_STATUS,
  type Atividade,
  type Cliente,
  type CnaeSecundario,
  type ClienteForm,
  type DadosCnpj,
  type Regime,
  type StatusCliente,
} from "@/lib/tipos";

import { BuscaCnpj } from "./BuscaCnpj";
import { SeletorNatureza } from "./SeletorNatureza";
import { SelecaoAtividade } from "./SelecaoAtividade";
import { Botao, Campo, MensagemErro, Rotulo, Selecao, classeCampo } from "./ui";

const vazio = (v: string) => (v.trim() === "" ? null : v.trim());

export function FormCliente({
  inicial,
  textoBotao,
  onSalvar,
}: {
  inicial?: Cliente;
  textoBotao: string;
  onSalvar: (dados: ClienteForm) => Promise<void>;
}) {
  const [cnpj, setCnpj] = useState(inicial?.cnpj ? mascaraCnpj(inicial.cnpj) : "");
  const [f, setF] = useState({
    razao_social: inicial?.razao_social ?? "",
    nome_fantasia: inicial?.nome_fantasia ?? "",
    cnae_principal: inicial?.cnae_principal ?? "",
    cnae_descricao: inicial?.cnae_descricao ?? "",
    municipio: inicial?.municipio ?? "",
    uf: inicial?.uf ?? "",
    atividade: (inicial?.atividade ?? "") as Atividade | "",
    regime_atual: (inicial?.regime_atual ?? "") as Regime | "",
    status: (inicial?.status ?? "prospect") as StatusCliente,
    contato_nome: inicial?.contato_nome ?? "",
    email: inicial?.email ?? "",
    telefone: inicial?.telefone ?? "",
    observacoes: inicial?.observacoes ?? "",
  });
  const [natureza, setNatureza] = useState({ descricao: inicial?.natureza_juridica ?? "", codigo: inicial?.natureza_juridica_codigo ?? "" });
  const [secundarios, setSecundarios] = useState<CnaeSecundario[] | null>(inicial?.cnaes_secundarios ?? null);
  const [dica, setDica] = useState("");
  const [erro, setErro] = useState("");
  const [salvando, setSalvando] = useState(false);
  const muda = (campo: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) =>
    setF((x) => ({ ...x, [campo]: e.target.value }));

  function preencher(d: DadosCnpj) {
    setF((x) => ({
      ...x,
      razao_social: d.razao_social,
      nome_fantasia: d.nome_fantasia ?? "",
      cnae_principal: d.cnae_principal ?? "",
      cnae_descricao: d.cnae_descricao ?? "",
      municipio: d.municipio ?? "",
      uf: d.uf ?? "",
      email: d.email ?? x.email,
      telefone: d.telefone ?? x.telefone,
      atividade: d.atividade_sugerida ?? x.atividade,
      regime_atual: d.regime_sugerido ?? x.regime_atual,
    }));
    setSecundarios(d.cnaes_secundarios);
    if (d.natureza_juridica) setNatureza({ descricao: d.natureza_juridica, codigo: d.natureza_juridica_codigo ?? "" });
    setDica(d.atividade_justificativa);
  }

  async function enviar(e: React.FormEvent) {
    e.preventDefault();
    setErro("");
    if (cnpj && !cnpjValido(cnpj)) return setErro("CNPJ inválido.");
    setSalvando(true);
    try {
      await onSalvar({
        razao_social: f.razao_social.trim(),
        nome_fantasia: vazio(f.nome_fantasia),
        cnpj: cnpj ? soDigitos(cnpj) : null,
        cnae_principal: vazio(f.cnae_principal),
        cnae_descricao: vazio(f.cnae_descricao),
        cnaes_secundarios: secundarios,
        natureza_juridica: natureza.descricao || null,
        natureza_juridica_codigo: natureza.descricao && natureza.codigo ? natureza.codigo : null,
        municipio: vazio(f.municipio),
        uf: vazio(f.uf)?.toUpperCase() ?? null,
        atividade: f.atividade || null,
        regime_atual: f.regime_atual || null,
        status: f.status,
        contato_nome: vazio(f.contato_nome),
        email: vazio(f.email),
        telefone: vazio(f.telefone),
        observacoes: vazio(f.observacoes),
      });
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Falha ao salvar");
    } finally {
      setSalvando(false);
    }
  }

  return (
    <form onSubmit={enviar} className="flex flex-col gap-4">
      <div className="grid gap-4 sm:grid-cols-2">
        <BuscaCnpj valor={cnpj} onChange={setCnpj} onEncontrado={preencher} />
        <Selecao rotulo="Situação" name="status" value={f.status} onChange={muda("status")}>
          {Object.entries(ROTULO_STATUS).map(([v, r]) => (
            <option key={v} value={v}>{r}</option>
          ))}
        </Selecao>
        <Campo rotulo="Razão social" name="razao_social" required minLength={2} value={f.razao_social} onChange={muda("razao_social")} />
        <Campo rotulo="Nome fantasia" name="nome_fantasia" value={f.nome_fantasia} onChange={muda("nome_fantasia")} />
        <SelecaoAtividade
          rotulo="Atividade (para os cálculos)"
          name="atividade"
          value={(f.atividade ?? "") as Atividade | ""}
          onChange={(v) => setF((x) => ({ ...x, atividade: v }))}
          vazio="Selecione…"
          ajuda={dica}
        />
        <Selecao rotulo="Regime atual" name="regime_atual" value={f.regime_atual} onChange={muda("regime_atual")}>
          <option value="">Não informado</option>
          {Object.entries(ROTULO_REGIME).map(([v, r]) => (
            <option key={v} value={v}>{r}</option>
          ))}
        </Selecao>
        <SeletorNatureza valor={natureza.descricao} onChange={(descricao) => setNatureza((n) => ({ descricao, codigo: descricao === n.descricao ? n.codigo : "" }))} />
        <Campo rotulo="CNAE principal" name="cnae_principal" maxLength={7} value={f.cnae_principal} onChange={muda("cnae_principal")} ajuda={[f.cnae_descricao, secundarios?.length ? `${secundarios.length} CNAE(s) secundário(s) da Receita guardados` : ""].filter(Boolean).join(" · ") || undefined} />
        <div className="grid grid-cols-[1fr_80px] gap-2">
          <Campo rotulo="Município" name="municipio" value={f.municipio} onChange={muda("municipio")} />
          <Campo rotulo="UF" name="uf" maxLength={2} value={f.uf} onChange={muda("uf")} />
        </div>
        <Campo rotulo="Contato" name="contato_nome" value={f.contato_nome} onChange={muda("contato_nome")} />
        <Campo rotulo="E-mail" name="email" type="email" value={f.email} onChange={muda("email")} />
        <Campo rotulo="Telefone" name="telefone" value={f.telefone} onChange={muda("telefone")} />
      </div>
      <div>
        <Rotulo htmlFor="observacoes">Observações</Rotulo>
        <textarea id="observacoes" rows={3} className={`${classeCampo} h-auto py-2`} value={f.observacoes} onChange={muda("observacoes")} />
      </div>
      <MensagemErro>{erro}</MensagemErro>
      <div>
        <Botao type="submit" carregando={salvando}>{textoBotao}</Botao>
      </div>
    </form>
  );
}
