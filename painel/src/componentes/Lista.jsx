import { useEffect, useState } from "react";
import { api, baixarCsv } from "../api.js";
import { CLASSES, GRUPOS, ORDEM_STATUS, STATUS, classe as rotuloClasse, data, porcentagem } from "../rotulos.js";
import Selo from "./Selo.jsx";

const POR_PAGINA = 50;
const PRESETS = {
  aguardando: { rotulo: "Aguardando gestão", status: GRUPOS.aguardando.status },
  ativa: { rotulo: "Ativas", status: GRUPOS.ativa.status },
  encerrada: { rotulo: "Encerradas", status: GRUPOS.encerrada.status },
  todas: { rotulo: "Todas", status: [] },
};

export default function Lista({ versao, aoSelecionar }) {
  const [preset, setPreset] = useState("aguardando");
  const [status, setStatus] = useState(PRESETS.aguardando.status);
  const [classe, setClasse] = useState("");
  const [busca, setBusca] = useState("");
  const [buscaAplicada, setBuscaAplicada] = useState("");
  const [itens, setItens] = useState([]);
  const [total, setTotal] = useState(0);
  const [limite, setLimite] = useState(POR_PAGINA);
  const [erro, setErro] = useState("");
  const [carregando, setCarregando] = useState(true);

  // aplica a busca digitada depois de uma pausa curta
  useEffect(() => {
    const t = setTimeout(() => setBuscaAplicada(busca), 350);
    return () => clearTimeout(t);
  }, [busca]);

  useEffect(() => {
    let ativo = true;
    setCarregando(true);
    api("/admin/ocorrencias", { params: { status, classe, busca: buscaAplicada, limite } })
      .then((r) => {
        if (!ativo) return;
        setItens(r.itens);
        setTotal(r.total);
        setErro("");
      })
      .catch((e) => ativo && setErro(e.message))
      .finally(() => ativo && setCarregando(false));
    return () => {
      ativo = false;
    };
  }, [status, classe, buscaAplicada, limite, versao]);

  function escolherPreset(chave) {
    setPreset(chave);
    setStatus(PRESETS[chave].status);
    setLimite(POR_PAGINA);
  }

  function alternarStatus(s) {
    setPreset("");
    setStatus((atual) => (atual.includes(s) ? atual.filter((x) => x !== s) : [...atual, s]));
    setLimite(POR_PAGINA);
  }

  return (
    <section className="visao-lista">
      <div className="filtros" role="group" aria-label="Filtros das ocorrências">
        <div className="segmentado" role="radiogroup" aria-label="Situação">
          {Object.entries(PRESETS).map(([chave, p]) => (
            <button
              key={chave}
              type="button"
              role="radio"
              aria-checked={preset === chave}
              className={preset === chave ? "segmento ativo" : "segmento"}
              onClick={() => escolherPreset(chave)}
            >
              {p.rotulo}
            </button>
          ))}
        </div>
        <select value={classe} onChange={(e) => setClasse(e.target.value)} aria-label="Classe">
          <option value="">Todas as classes</option>
          {Object.entries(CLASSES).map(([k, c]) => (
            <option key={k} value={k}>
              {c.rotulo}
            </option>
          ))}
        </select>
        <input
          type="search"
          placeholder="Buscar protocolo ou descrição"
          value={busca}
          onChange={(e) => setBusca(e.target.value)}
          aria-label="Buscar"
        />
        <button type="button" className="botao" onClick={() => baixarCsv().catch((e) => setErro(e.message))}>
          Exportar CSV
        </button>
      </div>

      <div className="chips" aria-label="Status incluídos">
        {ORDEM_STATUS.map((s) => (
          <button
            key={s}
            type="button"
            className={status.includes(s) ? "chip ativo" : "chip"}
            aria-pressed={status.includes(s)}
            onClick={() => alternarStatus(s)}
          >
            {STATUS[s].rotulo}
          </button>
        ))}
        <span className="muted pequeno">{status.length === 0 ? "nenhum filtro de status: todas" : ""}</span>
      </div>

      {erro && (
        <p className="erro" role="alert">
          {erro}
        </p>
      )}

      <div className="cartao tabela-moldura">
        <table className="tabela">
          <thead>
            <tr>
              <th>Protocolo</th>
              <th>Classe</th>
              <th>Cidadão × modelo</th>
              <th className="num">Confiança</th>
              <th>Status</th>
              <th>Reportada em</th>
            </tr>
          </thead>
          <tbody>
            {itens.map((o) => (
              <tr
                key={o.id}
                tabIndex={0}
                onClick={() => aoSelecionar(o.id)}
                onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && aoSelecionar(o.id)}
              >
                <td className="mono">{o.protocolo}</td>
                <td>{rotuloClasse(o.classe_final)}</td>
                <td>
                  {o.classe_detectada === null ? (
                    <span className="muted">sem detecção</span>
                  ) : o.classe_detectada === o.classe_informada ? (
                    "concordam"
                  ) : (
                    <span className="divergencia">divergem</span>
                  )}
                </td>
                <td className="num">{porcentagem(o.confianca)}</td>
                <td>
                  <Selo status={o.status} />
                </td>
                <td>{data(o.criado_em)}</td>
              </tr>
            ))}
            {!carregando && itens.length === 0 && (
              <tr>
                <td colSpan={6} className="vazio">
                  Nenhuma ocorrência com esses filtros.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="rodape-lista">
        <span className="muted">
          {carregando ? "Carregando…" : `${itens.length} de ${total} ocorrência${total === 1 ? "" : "s"}`}
        </span>
        {itens.length < total && (
          <button type="button" className="botao" onClick={() => setLimite((l) => l + POR_PAGINA)}>
            Carregar mais
          </button>
        )}
      </div>
    </section>
  );
}
