// Textos e agrupamentos exibidos no painel.

export const STATUS = {
  recebida: { rotulo: "Recebida", grupo: "aguardando" },
  classificada: { rotulo: "Classificada pelo modelo", grupo: "aguardando" },
  em_triagem: { rotulo: "Em triagem", grupo: "aguardando" },
  validada: { rotulo: "Validada", grupo: "ativa" },
  em_atendimento: { rotulo: "Em atendimento", grupo: "ativa" },
  resolvida: { rotulo: "Resolvida", grupo: "encerrada" },
  rejeitada: { rotulo: "Rejeitada", grupo: "encerrada" },
};
export const ORDEM_STATUS = Object.keys(STATUS);

// Os grupos definem a cor no mapa: o que pede acao do gestor, o que esta
// ativo como geocerca (gera alertas) e o que ja foi encerrado.
export const GRUPOS = {
  aguardando: { rotulo: "Aguardando gestão", status: ["recebida", "classificada", "em_triagem"] },
  ativa: { rotulo: "Ativa (gera alertas)", status: ["validada", "em_atendimento"] },
  encerrada: { rotulo: "Encerrada", status: ["resolvida", "rejeitada"] },
};

export const CLASSES = {
  buraco: { rotulo: "Buraco na via", sigla: "B" },
  calcada_danificada: { rotulo: "Calçada danificada", sigla: "C" },
};

export const ACOES = {
  validada: "Validar",
  em_triagem: "Enviar para triagem",
  em_atendimento: "Iniciar atendimento",
  resolvida: "Marcar como resolvida",
  rejeitada: "Rejeitar",
};

export const MOTIVOS = {
  confianca_acima_do_limiar: "confiança acima do limiar",
  baixa_confianca: "confiança abaixo do limiar",
  divergencia_cidadao_modelo: "modelo discorda da classe informada",
  sem_deteccao: "nenhum problema detectado na foto",
  modelo_indisponivel: "modelo indisponível",
};

const FORMATO_DATA = new Intl.DateTimeFormat("pt-BR", {
  dateStyle: "short",
  timeStyle: "short",
  timeZone: "America/Fortaleza",
});

export function data(iso) {
  return iso ? FORMATO_DATA.format(new Date(iso)) : "–";
}

export function porcentagem(valor, casas = 0) {
  if (valor === null || valor === undefined) return "–";
  return valor.toLocaleString("pt-BR", { style: "percent", maximumFractionDigits: casas });
}

export function numero(valor, casas = 0) {
  if (valor === null || valor === undefined) return "–";
  return valor.toLocaleString("pt-BR", { maximumFractionDigits: casas });
}

export function horas(valor) {
  if (valor === null || valor === undefined) return "–";
  if (valor < 1) return `${Math.round(valor * 60)} min`;
  if (valor < 48) return `${numero(valor, 1)} h`;
  return `${numero(valor / 24, 1)} dias`;
}

export function classe(chave) {
  return CLASSES[chave]?.rotulo ?? chave ?? "–";
}

export function grupoDoStatus(status) {
  return STATUS[status]?.grupo ?? "encerrada";
}
