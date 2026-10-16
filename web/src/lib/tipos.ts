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
  honorarios: HonorariosConfig | null;
}

export type RegimeHonorarios = "mei" | "simples" | "presumido" | "real";

/** Tabela de honorários do escritório (valores mensais, exceto a adesão). */
export interface HonorariosConfig {
  base: Partial<Record<RegimeHonorarios, number>>;
  por_funcionario: number;
  adesao: number;
  servicos: string;
  validade_dias: number;
}

/** Proposta de honorários anexada a uma simulação. */
export interface Honorarios {
  funcionarios: number;
  valor_mensal: number;
  adesao: number;
  servicos: string;
  validade_dias: number;
  definido_em: string;
  valido_ate: string;
}

export interface SugestaoHonorarios {
  configurado: boolean;
  regime: RegimeHonorarios | null;
  base: number;
  por_funcionario: number;
  funcionarios: number;
  valor_mensal: number;
  adesao: number;
  servicos: string;
  validade_dias: number;
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

export type TipoSimulacao = "expressa" | "completa" | "reforma" | "simples_reforma" | "autonomo" | "pro_labore" | "recuperacao";

export const ROTULO_TIPO: Record<TipoSimulacao, string> = {
  expressa: "Expressa",
  completa: "Planejamento",
  reforma: "Reforma",
  simples_reforma: "Simples na Reforma",
  autonomo: "Autônomo × CNPJ",
  pro_labore: "Pró-labore",
  recuperacao: "Recuperação de tributos",
};

export interface Simulacao {
  id: number;
  cliente_id: number;
  tipo: TipoSimulacao;
  titulo: string;
  entrada: Record<string, unknown>;
  // O formato do resultado depende do tipo (Comparativo, ResultadoReforma, ...)
  resultado: Comparativo & { melhor: string; economia_vs_pior: number };
  versao_motor: string;
  publicada: boolean;
  publicada_em?: string | null;
  honorarios?: Honorarios | null;
  visto_primeira_em?: string | null;
  visto_ultima_em?: string | null;
  aberturas?: number;
  aceite_em?: string | null;
  aceite_nome?: string | null;
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

// --- Fase 2 ----------------------------------------------------------------------
export interface BlocoCalculo {
  tributos: { nome: string; valor: number }[];
  memoria: PassoMemoria[];
  alertas: string[];
}

export interface AnoReforma extends BlocoCalculo {
  ano: number;
  total: number;
  carga: number;
  atuais: number;
  novos: number;
}

export interface ResultadoReforma {
  base_venda: number;
  base_credito: number;
  cbs_referencia: number;
  ibs_referencia: number;
  anos: AnoReforma[];
  variacao_total: number;
  variacao_carga_pp: number;
  melhor: string;
  alertas: string[];
}

export interface CenarioSimplesReforma extends BlocoCalculo {
  ano: number;
  dentro_do_das: number;
  por_fora: number;
  diferenca: number;
  equilibrio_b2b: number | null;
  equilibrio_texto: string;
  credito_cliente_dentro: number;
  credito_cliente_fora: number;
  recomendacao: string;
}

export interface ResultadoSimplesReforma {
  cenarios: CenarioSimplesReforma[];
  curvas: Record<string, { b2b: number; diferenca: number }[]>;
  percentual_b2b: number;
  melhor: string;
}

export interface OpcaoAutonomo extends BlocoCalculo {
  nome: string;
  aplicavel: boolean;
  tributos_mensais: number;
  custos_mensais: number;
  liquido_mensal: number;
  detalhe: string;
}

export interface ResultadoAutonomo {
  opcoes: OpcaoAutonomo[];
  receita_mensal: number;
  melhor: string;
  ranking: string[];
  ganho_vs_autonomo_anual: number;
  alertas: string[];
}

export interface CenarioProLabore extends BlocoCalculo {
  descricao: string;
  pro_labore: number;
  dividendos: number;
  custo_mensal: number;
  liquido_mensal: number;
}

export interface ResultadoProLabore {
  cenarios: CenarioProLabore[];
  regime: string;
  economia_mensal: number;
  economia_anual: number;
  melhor: string;
}

export interface ResultadoSalario extends BlocoCalculo {
  salario_bruto: number;
  liquido: number;
}

// --- Equipe, envio, portal e movimento fiscal --------------------------------------------
export interface Membro {
  id: number;
  nome: string;
  email: string;
  papel: "admin" | "membro";
  ativo: boolean;
  criado_em: string;
}

export interface Convite {
  id: number;
  email: string;
  nome: string | null;
  papel: string | null;
  expira_em: string;
  criado_em: string;
}

export interface Envio {
  id: number;
  para: string;
  assunto: string;
  status: "enviado" | "falhou";
  erro: string | null;
  criado_em: string;
}

export interface PortalEstado {
  ativo: boolean;
  criado_em: string | null;
  ultimo_acesso_em: string | null;
  publicadas: number;
}

export interface MesMovimento {
  competencia: string;
  saidas: number;
  entradas: number;
  icms: number;
  ipi: number;
  pis: number;
  cofins: number;
  documentos: number;
}

export interface Movimento {
  meses: MesMovimento[];
  receita_12m: number;
  compras_12m: number;
  meses_12m: number;
  documentos: number;
}

export interface ResultadoImportacao {
  importados: number;
  duplicados: number;
  atualizados: number;
  ignorados: { arquivo: string; motivo: string }[];
  total_ignorados: number;
  competencias: string[];
}

// --- Recuperação de tributos (monofásico e ST) --------------------------------------------
export interface MesRecuperacao {
  competencia: string;
  receita: number;
  base_monofasico: number;
  base_st: number;
  base_verificar: number;
  rbt12: number;
  rbt12_estimado: boolean;
  faixa: number;
  aliquota_efetiva: number;
  pis_cofins: number;
  icms: number;
  provavel: number;
  a_verificar: number;
  calculado: boolean;
}

export interface ProdutoRecuperacao {
  ncm: string | null;
  descricao: string | null;
  grupo: string | null;
  base_legal: string | null;
  observacao: string | null;
  monofasico: string | null;
  st: string | null;
  certeza: "provavel" | "verificar";
  valor: number;
  itens: number;
}

export interface ResultadoRecuperacao {
  disponivel: boolean;
  anexo: "I" | "II";
  anexo_origem: "escolhido" | "atividade" | "padrao";
  periodo: { inicio: string | null; fim: string | null; meses: number };
  documentos_sem_itens: number;
  meses: MesRecuperacao[];
  totais: { pis_cofins: number; icms: number; provavel: number; a_verificar: number; base_monofasico: number; base_st: number };
  economia_anual: number;
  produtos: ProdutoRecuperacao[];
  tributos: { nome: string; valor: number }[];
  memoria: PassoMemoria[];
  alertas: string[];
  melhor: string;
  economia_vs_pior: number;
}

// --- Avisos da carteira e mudanças na legislação ----------------------------------------------
export type Gravidade = "critico" | "atencao" | "oportunidade" | "info";

export interface AvisoCarteira {
  id: string;
  codigo: string;
  gravidade: Gravidade;
  titulo: string;
  detalhe: string;
  valor: number | null;
  base_legal: string;
  cliente_id: number;
  cliente: string;
  acao: { tipo: "cliente" | "recalcular"; rotulo: string; aba?: string; simulacao_id?: number };
}

export interface RespostaAvisos {
  avisos: AvisoCarteira[];
  resumo: Record<Gravidade, number> & { total: number; valor_oportunidades: number };
  clientes_analisados: number;
}

export interface MudancaLegal {
  id: string;
  data: string;
  titulo: string;
  resumo: string;
  base_legal: string;
  areas: string[];
  efeito: string;
  observacao?: string;
  vigente: boolean;
  dias: number;
}

/** Presente no resultado de uma simulação recalculada com as regras atuais. */
export interface InfoRecalculo {
  de: number;
  em: string;
  antes: { melhor: string | null; economia_vs_pior: number | null };
  /** O que mudou, em palavras (totais por regime e recomendação), quando a API consegue descrever. */
  resumo?: string | null;
}

// --- Caixa de envio de notas ---------------------------------------------------------------------
export interface CaixaEstado {
  ativo: boolean;
  criado_em: string | null;
  ultimo_envio_em: string | null;
  total_envios: number;
  total_notas: number;
}

export interface FinanceiroPrevia {
  cabecalhos: string[];
  amostra: string[][];
  total_linhas: number;
  sugestao: Record<string, number | null>;
  rotulos: Record<string, string>;
}

export interface FinanceiroMes {
  competencia: string;
  receita: number | null;
  compras: number | null;
  folha: number | null;
  pro_labore: number | null;
  despesas_creditaveis: number | null;
  outras_despesas: number | null;
}

export interface FinanceiroImportacao {
  meses_novos: number;
  meses_atualizados: number;
  competencias: string[];
  ignoradas: { linha: number; motivo: string }[];
  total_ignoradas: number;
  avisos: string[];
}

export interface FinanceiroPlanejamento {
  meses: number;
  anualizado: boolean;
  periodo_inicio: string;
  periodo_fim: string;
  receita_bruta_anual: number;
  compras_anual: number;
  folha_clt_anual: number;
  pro_labore_anual: number;
  despesas_creditaveis_anual: number;
  outras_despesas_anual: number;
}

export interface Financeiro {
  meses: FinanceiroMes[];
  planejamento: FinanceiroPlanejamento | null;
}
