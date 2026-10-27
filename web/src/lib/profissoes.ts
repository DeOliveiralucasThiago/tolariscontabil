/** Profissões da redução de 30% do IBS e da CBS (LC 214/2025, art. 127, incisos I a XVIII). O rol é fechado. */
export const PROFISSOES_ART_127 = [
  "Administradores",
  "Advogados",
  "Arquitetos e urbanistas",
  "Assistentes sociais",
  "Bibliotecários",
  "Biólogos",
  "Contabilistas",
  "Economistas",
  "Economistas domésticos",
  "Profissionais de educação física",
  "Engenheiros e agrônomos",
  "Estatísticos",
  "Médicos veterinários e zootecnistas",
  "Museólogos",
  "Químicos",
  "Profissionais de relações públicas",
  "Técnicos industriais",
  "Técnicos agrícolas",
] as const;

export const PROFISSAO_SAUDE = "saude";
export const PROFISSAO_OUTRA = "outra";

/** Redução de alíquota sugerida para a profissão escolhida: 30% (art. 127), 60% (serviços de saúde, art. 130) ou nenhuma. */
export function reducaoDaProfissao(profissao: string): number {
  if (!profissao || profissao === PROFISSAO_OUTRA) return 0;
  if (profissao === PROFISSAO_SAUDE) return 0.6;
  return 0.3;
}
