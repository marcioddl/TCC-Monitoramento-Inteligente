// Cliente da API do MIIU. Caminhos relativos: em producao o painel e servido
// pelo proprio FastAPI; em desenvolvimento o Vite repassa as chamadas.
const BASE = import.meta.env.VITE_API_URL ?? "";
const CHAVE_TOKEN = "miiu.painel.token";

let token = ler();
let aoExpirar = () => {};

function ler() {
  try {
    const salvo = JSON.parse(localStorage.getItem(CHAVE_TOKEN) ?? "null");
    if (salvo && new Date(salvo.expira_em) > new Date()) return salvo.token;
  } catch {
    /* armazenamento indisponivel: segue sem sessao salva */
  }
  return null;
}

export class ErroApi extends Error {
  constructor(status, mensagem) {
    super(mensagem);
    this.status = status;
  }
}

export const sessao = {
  ativa: () => Boolean(token),
  aoExpirar(fn) {
    aoExpirar = fn;
  },
  async entrar(senha) {
    const resposta = await fetch(`${BASE}/admin/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ senha }),
    });
    if (resposta.status === 401) throw new ErroApi(401, "Senha incorreta.");
    if (!resposta.ok) throw new ErroApi(resposta.status, "Não foi possível entrar. A API está no ar?");
    const dados = await resposta.json();
    token = dados.token;
    try {
      localStorage.setItem(CHAVE_TOKEN, JSON.stringify(dados));
    } catch {
      /* sem armazenamento: a sessao dura ate recarregar a pagina */
    }
  },
  sair() {
    token = null;
    try {
      localStorage.removeItem(CHAVE_TOKEN);
    } catch {
      /* nada a fazer */
    }
    aoExpirar();
  },
};

export function urlDaApi(caminho) {
  return `${BASE}${caminho}`;
}

function montarUrl(caminho, params) {
  const url = new URL(`${BASE}${caminho}`, window.location.origin);
  for (const [chave, valor] of Object.entries(params ?? {})) {
    if (Array.isArray(valor)) valor.forEach((v) => url.searchParams.append(chave, v));
    else if (valor !== undefined && valor !== null && valor !== "") url.searchParams.set(chave, valor);
  }
  return url;
}

export async function api(caminho, { metodo = "GET", corpo, params, bruto = false } = {}) {
  const resposta = await fetch(montarUrl(caminho, params), {
    method: metodo,
    headers: {
      ...(corpo ? { "Content-Type": "application/json" } : {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: corpo ? JSON.stringify(corpo) : undefined,
  });
  if (resposta.status === 401) {
    sessao.sair();
    throw new ErroApi(401, "Sessão expirada. Entre novamente.");
  }
  if (!resposta.ok) {
    let detalhe = `Erro ${resposta.status}`;
    try {
      const corpoErro = await resposta.json();
      if (typeof corpoErro.detail === "string") detalhe = corpoErro.detail;
    } catch {
      /* resposta sem JSON */
    }
    throw new ErroApi(resposta.status, detalhe);
  }
  return bruto ? resposta : resposta.json();
}

export async function baixarCsv() {
  const resposta = await api("/admin/exportar.csv", { bruto: true });
  const blob = await resposta.blob();
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = `ocorrencias_miiu_${new Date().toISOString().slice(0, 10)}.csv`;
  link.click();
  setTimeout(() => URL.revokeObjectURL(link.href), 1000);
}
