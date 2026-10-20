/** Conteúdo do tour de ajuda. O alvo de cada passo é um seletor CSS ou "texto:Rótulo" (link/botão/aba com esse texto). */

export interface Passo {
  /** Seletor CSS ou "texto:Importar planilha". Sem alvo (ou alvo ausente), o balão aparece no centro da tela. */
  alvo?: string;
  titulo: string;
  texto: string;
  /** O alvo está no menu lateral, que no celular fica fechado: o tour abre o menu antes de mostrar. */
  menu?: boolean;
}

const menu = (rota: string) => `[data-tour="menu-${rota}"]`;
const cartao = (nome: string) => `[data-tour="cartao-${nome}"]`;
const aba = (id: string) => `[data-tour="aba-${id}"]`;

export const TOUR_GERAL: Passo[] = [
  {
    titulo: "Bem-vindo ao Tolaris Contábil",
    texto:
      "Em cerca de um minuto, mostramos para que serve cada menu. O Tolaris ajuda a escolher o melhor regime tributário dos seus clientes, " +
      "acompanhar a carteira, receber notas sem digitar e fechar mais propostas de honorários. Use as setas do teclado ou os botões; Esc fecha.",
  },
  {
    alvo: menu("/painel"), menu: true, titulo: "Painel",
    texto: "A visão geral da carteira: clientes ativos, prospects, simulações do mês e os avisos mais importantes, tudo numa tela só.",
  },
  {
    alvo: menu("/prospeccao"), menu: true, titulo: "Prospecção",
    texto: "Para um possível cliente: digite o CNPJ, o faturamento e a folha e veja em segundos qual regime compensa, com um PDF com a marca do seu escritório para levar à reunião.",
  },
  {
    alvo: menu("/clientes"), menu: true, titulo: "Clientes",
    texto:
      "A sua carteira. Dentro de cada cliente ficam as simulações, o planejamento completo, o movimento fiscal (notas e planilhas), o acompanhamento e os dados. " +
      "Para começar rápido, use Importar planilha e cadastre todos de uma vez só com o CNPJ.",
  },
  {
    alvo: menu("/funil"), menu: true, titulo: "Funil comercial",
    texto: "Acompanhe as propostas de honorários: quantas foram criadas, enviadas, abertas pelo cliente e aceitas, quanto isso vale por mês e quem precisa de um lembrete.",
  },
  {
    alvo: menu("/avisos"), menu: true, titulo: "Avisos",
    texto:
      "O que merece a sua atenção hoje: fator R, clientes perto dos limites do MEI e do Simples, imposto pago a mais em produtos monofásicos, " +
      "mudanças na lei que alteram planejamentos já feitos e propostas paradas.",
  },
  {
    alvo: menu("/reforma"), menu: true, titulo: "Reforma Tributária",
    texto: "Simule a transição de 2026 a 2033 (CBS e IBS) para um cliente e veja se, no Simples, compensa recolher IBS e CBS por dentro ou por fora do DAS.",
  },
  {
    alvo: menu("/pessoa-fisica"), menu: true, titulo: "Pessoa física",
    texto: "Calculadoras de pró-labore × dividendos, salário líquido e autônomo × CNPJ, com as regras de 2026 e a memória de cálculo.",
  },
  {
    alvo: menu("/equipe"), menu: true, titulo: "Equipe",
    texto: "Convide colegas por e-mail e defina quem é administrador. Cada pessoa entra com a própria senha, e dá para ligar a verificação em duas etapas.",
  },
  {
    alvo: menu("/configuracoes"), menu: true, titulo: "Configurações",
    texto:
      "Logo e cor do escritório (aparecem nos PDFs), tabela de honorários, caixa de e-mail para receber notas, segurança da conta e o registro de atividades. " +
      "Vale começar por aqui.",
  },
  {
    titulo: "Pronto para começar",
    texto:
      "Um bom primeiro passo: em Configurações, coloque a logo e a tabela de honorários; depois, em Clientes, use Importar planilha ou faça uma Prospecção. " +
      "Em qualquer tela, o botão ? Ajuda (canto da tela) explica os botões daquela página e refaz este tour.",
  },
];

const PAGINAS: { rota: RegExp; passos: Passo[] }[] = [
  {
    rota: /^\/painel$/,
    passos: [
      { alvo: '[data-tour="titulo"]', titulo: "Painel", texto: "A situação da carteira num relance: quantos clientes ativos e prospects, e quantas simulações foram feitas no mês." },
      { alvo: cartao("avisos-da-carteira"), titulo: "Avisos da carteira", texto: "Os avisos mais urgentes de todos os clientes. Clique para abrir a tela Avisos, com filtros e a ação de cada um." },
      { alvo: cartao("ultimas-simulacoes"), titulo: "Últimas simulações", texto: "Atalho para os últimos relatórios. Clique no cliente para abrir; de lá você baixa o PDF, envia por e-mail ou publica no portal." },
      { alvo: "texto:Nova prospecção", titulo: "Nova prospecção", texto: "Começa uma simulação para um possível cliente, sem precisar cadastrá-lo antes." },
    ],
  },
  {
    rota: /^\/prospeccao$/,
    passos: [
      { alvo: cartao("empresa"), titulo: "Dados da empresa", texto: "Digite o CNPJ e busque: razão social, CNAE e a atividade sugerida vêm da Receita. Confira a atividade, porque ela define o anexo do Simples." },
      { alvo: cartao("numeros-do-mes"), titulo: "Números do mês", texto: "Faturamento e folha mensais bastam para uma primeira comparação entre Simples, Lucro Presumido e Lucro Real." },
      { alvo: "texto:Calcular previsão", titulo: "Calcular", texto: "Mostra o melhor regime, a economia e a memória de cálculo passo a passo. Depois você salva no cliente, baixa o PDF com a sua marca e pode enviar ao prospect." },
    ],
  },
  {
    rota: /^\/clientes$/,
    passos: [
      { alvo: "texto:Importar planilha", titulo: "Importar planilha", texto: "Cadastre a carteira toda de uma vez: envie um .csv ou .xlsx com o CNPJ de cada cliente. O sistema completa razão social, CNAE e atividade pela Receita." },
      { alvo: "texto:Novo cliente", titulo: "Novo cliente", texto: "Cadastro individual, com busca pelo CNPJ." },
      { alvo: '[aria-label="Buscar por nome ou CNPJ"]', titulo: "Busca", texto: "Encontre um cliente por nome, nome fantasia ou CNPJ." },
      { alvo: '[aria-label="Filtrar por situação"]', titulo: "Situação", texto: "Prospect é quem ainda não contratou; Ativo, quem já é cliente; Inativo, quem saiu. O aviso de notas paradas só vale para os ativos." },
      { alvo: "table", titulo: "A lista", texto: "Clique no nome de um cliente para abrir as simulações, o movimento fiscal, o acompanhamento e os dados dele." },
    ],
  },
  {
    rota: /^\/clientes\/importar$/,
    passos: [
      { alvo: cartao("1-planilha"), titulo: "Planilha da carteira", texto: "Baixe a planilha modelo, preencha ao menos o CNPJ (razão social, atividade, regime, e-mail e telefone são opcionais) e envie." },
      { titulo: "Conferência antes de gravar", texto: "O sistema sugere as colunas, mostra quantos clientes são novos, quais já existem, quais estão repetidos e quais têm CNPJ inválido. Nada é gravado até você confirmar." },
      { titulo: "Completar pelo CNPJ", texto: "Quem entrou só com o CNPJ é completado em lotes pela consulta da Receita. Nada que você digitou é sobrescrito." },
    ],
  },
  {
    rota: /^\/clientes\/\d+$/,
    passos: [
      { alvo: aba("simulacoes"), titulo: "Simulações", texto: "Todos os relatórios do cliente: abra o PDF, envie por e-mail, publique no portal do cliente, monte a proposta de honorários e recalcule quando a lei mudar." },
      { alvo: aba("planejamento"), titulo: "Novo planejamento", texto: "Planejamento completo com valores anuais (folha, compras, despesas). É mais preciso que a simulação expressa; dá para preencher com notas ou planilha. Quem recebe de clientes no exterior informa a receita de exportação e a variação cambial no bloco opcional, com conversor de moeda pela PTAX." },
      { alvo: aba("movimento"), titulo: "Movimento fiscal", texto: "Importe XML e SPED, gere o link para o cliente enviar as notas sozinho, traga a planilha contábil e descubra imposto pago a mais em produtos monofásicos e com ST." },
      { alvo: aba("acompanhamento"), titulo: "Acompanhamento", texto: "Compara o que foi planejado com o que aconteceu, diz se a recomendação ainda vale e avisa em que mês o cliente passa de um limite de enquadramento." },
      { alvo: aba("dados"), titulo: "Dados cadastrais", texto: "Cadastro do cliente, situação (prospect, ativo, inativo) e, para administradores, a exportação de todos os dados e a exclusão definitiva (LGPD)." },
    ],
  },
  {
    rota: /^\/funil$/,
    passos: [
      { alvo: '[aria-label="Período"], select[name="periodo_funil"]', titulo: "Período", texto: "Escolha de que época contar as propostas. O funil usa a data de criação da proposta." },
      { alvo: cartao("funil"), titulo: "O funil", texto: "Quantas propostas chegaram a cada etapa e a conversão entre elas. “Enviada” é publicar no portal ou mandar por e-mail; “aberta” é o cliente abrir o relatório." },
      { alvo: cartao("propostas"), titulo: "Propostas", texto: "Ordenadas por urgência, com a ação sugerida: enviar, lembrar, ligar ou renovar. Clique no cliente para abrir a proposta." },
    ],
  },
  {
    rota: /^\/avisos$/,
    passos: [
      { alvo: '[data-tour="titulo"]', titulo: "Avisos", texto: "Reúne o que o Tolaris encontrou na carteira inteira: fator R, limites, imposto pago a mais, mudanças na lei e propostas paradas." },
      { alvo: '[role="tablist"]', titulo: "Filtros", texto: "Filtre por urgência: crítico, atenção, oportunidade ou informativo. Oportunidades são dinheiro a ganhar." },
      { titulo: "Ações", texto: "Cada aviso traz o valor em jogo e um botão: abrir o cliente, ver a análise ou recalcular uma simulação que mudou com a lei (a versão anterior fica no histórico)." },
    ],
  },
  {
    rota: /^\/reforma$/,
    passos: [
      { alvo: '[role="tablist"]', titulo: "Duas simulações", texto: "A transição de 2026 a 2033 mostra como CBS e IBS substituem PIS, Cofins, ICMS e ISS ano a ano. A outra decide, no Simples, entre IBS/CBS por dentro ou por fora do DAS." },
      { titulo: "Estimativas", texto: "As alíquotas de referência de CBS e IBS ainda são estimativas até o Senado fixar os valores oficiais. O relatório avisa isso." },
    ],
  },
  {
    rota: /^\/pessoa-fisica$/,
    passos: [
      { alvo: '[role="tablist"]', titulo: "Calculadoras", texto: "Pró-labore × dividendos para sócios, autônomo × CNPJ e salário líquido, com as regras de 2026 (IRPF e INSS) e memória de cálculo." },
    ],
  },
  {
    rota: /^\/equipe$/,
    passos: [
      { alvo: cartao("convidar"), titulo: "Convidar", texto: "Digite o e-mail e o papel: administradores alteram os dados do escritório e gerenciam a equipe; membros trabalham com os clientes. O convite vale por 7 dias." },
      { alvo: "table", titulo: "Membros", texto: "Troque papéis, desative quem saiu (a sessão cai na hora) e, se alguém perdeu o celular da verificação em duas etapas, redefina por aqui." },
    ],
  },
  {
    rota: /^\/configuracoes$/,
    passos: [
      { alvo: cartao("identificacao"), titulo: "Identificação", texto: "Nome, CNPJ, CRC e contato do escritório aparecem nos PDFs e nos e-mails enviados aos clientes." },
      { alvo: cartao("logo"), titulo: "Logo e cor", texto: "Envie a logo e escolha a cor da marca: os relatórios e o portal do cliente ficam com a cara do seu escritório." },
      { alvo: cartao("tabela-de-honorarios"), titulo: "Tabela de honorários", texto: "Valor base por regime, adicional por funcionário e adesão. O sistema sugere o valor da proposta de cada cliente; você ajusta antes de enviar." },
      { alvo: cartao("caixa-de-entrada-de-notas-e-mail"), titulo: "Caixa de e-mail de notas", texto: "Aponte uma caixa de e-mail do escritório: os XML e SPED que os clientes mandarem entram sozinhos no cliente certo, achado pelo CNPJ." },
      { alvo: cartao("verificacao-em-duas-etapas"), titulo: "Verificação em duas etapas", texto: "Ative com um aplicativo autenticador no celular: além da senha, o login pede um código. Guarde os códigos de recuperação." },
      { alvo: cartao("registro-de-atividades"), titulo: "Registro de atividades", texto: "Só para administradores: quem entrou, importou, exportou ou excluiu dados. Dá para filtrar e exportar em CSV." },
    ],
  },
];

export function passosDaPagina(caminho: string): Passo[] | null {
  return PAGINAS.find((p) => p.rota.test(caminho))?.passos ?? null;
}
