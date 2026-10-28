import { useCallback, useEffect, useState } from "react";
import { api, sessao } from "./api.js";
import Login from "./componentes/Login.jsx";
import Mapa from "./componentes/Mapa.jsx";
import Lista from "./componentes/Lista.jsx";
import Indicadores from "./componentes/Indicadores.jsx";
import Detalhe from "./componentes/Detalhe.jsx";

const VISOES = [
  { id: "mapa", rotulo: "Mapa" },
  { id: "lista", rotulo: "Ocorrências" },
  { id: "indicadores", rotulo: "Indicadores" },
];

function lerVisao() {
  const hash = window.location.hash.replace("#", "");
  return VISOES.some((v) => v.id === hash) ? hash : "mapa";
}

export default function App() {
  const [logado, setLogado] = useState(sessao.ativa());
  const [visao, setVisao] = useState(lerVisao);
  const [selecionada, setSelecionada] = useState(null);
  // incrementado a cada mudanca de status, para as visoes recarregarem
  const [versao, setVersao] = useState(0);
  const [saude, setSaude] = useState(null);

  useEffect(() => {
    sessao.aoExpirar(() => setLogado(false));
  }, []);

  useEffect(() => {
    const aoMudarHash = () => setVisao(lerVisao());
    window.addEventListener("hashchange", aoMudarHash);
    return () => window.removeEventListener("hashchange", aoMudarHash);
  }, []);

  useEffect(() => {
    if (!logado) return;
    api("/health").then(setSaude).catch(() => setSaude(null));
  }, [logado, versao]);

  const aoAlterar = useCallback(() => setVersao((v) => v + 1), []);

  if (!logado) return <Login aoEntrar={() => setLogado(true)} />;

  return (
    <div className="app">
      <header className="topo">
        <div className="marca">
          <strong>MIIU</strong>
          <span>Painel de gestão</span>
        </div>
        <nav className="abas" aria-label="Visões do painel">
          {VISOES.map((v) => (
            <a
              key={v.id}
              href={`#${v.id}`}
              className={visao === v.id ? "aba ativa" : "aba"}
              aria-current={visao === v.id ? "page" : undefined}
            >
              {v.rotulo}
            </a>
          ))}
        </nav>
        <div className="topo-direita">
          {saude && (
            <span className="estado-api" title={saude.modelo?.observacao ?? ""}>
              <span className={saude.modelo?.disponivel ? "ponto ok" : "ponto alerta"} aria-hidden="true" />
              {saude.modelo?.disponivel ? `Modelo ${saude.modelo.versao}` : "Modelo indisponível"}
              {" · "}
              Push {saude.notificacoes === "fcm" ? "FCM" : "simulado"}
            </span>
          )}
          <button type="button" className="botao discreto" onClick={() => sessao.sair()}>
            Sair
          </button>
        </div>
      </header>

      <main className="conteudo">
        {visao === "mapa" && <Mapa versao={versao} aoSelecionar={setSelecionada} />}
        {visao === "lista" && <Lista versao={versao} aoSelecionar={setSelecionada} />}
        {visao === "indicadores" && <Indicadores versao={versao} />}
      </main>

      {selecionada && (
        <Detalhe
          id={selecionada}
          aoFechar={() => setSelecionada(null)}
          aoAlterar={aoAlterar}
          aoSelecionar={setSelecionada}
        />
      )}
    </div>
  );
}
