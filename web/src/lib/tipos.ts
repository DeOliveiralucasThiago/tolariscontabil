export type Atividade =
  | "comercio"
  | "industria"
  | "servico_anexo_iii"
  | "servico_anexo_iv"
  | "servico_fator_r";

export type StatusCliente = "prospect" | "ativo" | "inativo";
export type Regime = "mei" | "simples" | "presumido" | "real" | "outro";

export const ATIVIDADES: { valor: Atividade; rotulo: string; ajuda: string }[] = [
  { valor: "comercio", rotulo: "Comércio", ajuda: "Revenda de mercadorias (Anexo I)" },
  { valor: "industria", rotulo: "Indústria", ajuda: "Produção própria (Anexo II)" },
  { valor: "servico_fator_r", rotulo: "Serviços com fator R", ajuda: "TI, consultoria, saúde, engenharia (Anexo III ou V)" },
  { valor: "servico_anexo_iii", rotulo: "Serviços — Anexo III", ajuda: "Contabilidade, academias, agências, transporte" },
  { valor: "servico_anexo_iv", rotulo: "Serviços — Anexo IV", ajuda: "Construção, vigilância, limpeza, advocacia" },
];

export const ROTULO_ATIVIDADE: Record<string, string> = Object.fromEntries(
  ATIVIDADES.map((a) => [a.valor, a.rotulo]),
);

export const ROTULO_STATUS: Record<StatusCliente, string> = {
  prospect: "Prospect",
  ativo: "Ativo",
  inativo: "Inativo",
};

export const ROTULO_REGIME: Record<Regime, string> = {
  mei: "MEI",
  simples: "Simples Nacional",
  presumido: "Lucro Presumido",
  real: "Lucro Real",
  outro: "Outro",
};

export interface Usuario {
  id: number;
  nome: string;
  email: string;
  papel: string;
}

export interface Escritorio {
  id: number;
  nome: string;
  cnpj: string | null;
  contador_responsavel: string | null;
  crc: string | null;
  email: string | null;
  telefone: string | null;
  cor_primaria: string;
  tem_logo: boolean;
}

export interface Sessao {
  usuario: Usuario;
  escritorio: Escritorio;
}

export interface Cliente {
  id: number;
  razao_social: string;
  nome_fantasia: string | null;
  cnpj: string | null;
  cnae_principal: string | null;
  cnae_descricao: string | null;
  municipio: string | null;
  uf: string | null;
  atividade: Atividade | null;
  regime_atual: Regime | null;
  status: StatusCliente;
  contato_nome: string | null;
  email: string | null;
  telefone: string | null;
  observacoes: string | null;
  criado_em: string;
  atualizado_em: string;
  total_simulacoes: number;
  ultima_simulacao_em: string | null;
}

export type ClienteForm = Partial<Omit<Cliente, "id" | "criado_em" | "atualizado_em" | "total_simulacoes" | "ultima_simulacao_em">> & {
  razao_social: string;
};

export interface DadosCnpj {
  cnpj: string;
  razao_social: string;
  nome_fantasia: string | null;
  situacao: string | null;
  cnae_principal: string | null;
  cnae_descricao: string | null;
  municipio: string | null;
  uf: string | null;
  email: string | null;
  telefone: string | null;
  opcao_simples: boolean | null;
  opcao_mei: boolean | null;
  regime_sugerido: Regime | null;
  atividade_sugerida: Atividade | null;
  atividade_justificativa: string;
}

export interface PassoMemoria {
  descricao: string;
  formula: string;
  valor: number;
  base_legal: string;
}

export interface ResultadoRegime {
  titulo: string;
  aplicavel: boolean;
  total: number;
  carga_efetiva: number | null;
  tributos: { nome: string; valor: number }[];
  memoria: PassoMemoria[];
  alertas: string[];
}

export interface Comparativo {
  receita_anual: number;
  atividade: Atividade;
  ano: number;
  regimes: ResultadoRegime[];
  melhor: string;
  ranking: string[];
  economia_vs_segundo: number;
  economia_vs_pior: number;
  alertas: string[];
}

export interface Simulacao {
  id: number;
  cliente_id: number;
  tipo: "expressa" | "completa";
  titulo: string;
  entrada: Record<string, unknown>;
  resultado: Comparativo;
  versao_motor: string;
  criado_em: string;
}

export interface ExpressaEntrada {
  faturamento_mensal: number;
  folha_mensal: number;
  pro_labore_mensal: number;
  atividade: Atividade;
  ano?: number;
}

export interface CompletaEntrada {
  atividade: Atividade;
  receita_bruta_anual: number;
  folha_clt_anual: number;
  pro_labore_anual: number;
  compras_anual: number;
  despesas_creditaveis_anual: number;
  outras_despesas_anual: number;
  aliquota_iss: number;
  aliquota_icms: number;
  ano?: number;
}

export interface Painel {
  clientes_ativos: number;
  prospects: number;
  simulacoes_mes: number;
  economia_identificada_mes: number;
  ultimas_simulacoes: {
    id: number;
    cliente_id: number;
    cliente: string;
    titulo: string;
    melhor: string;
    economia: number;
    criado_em: string;
  }[];
}
