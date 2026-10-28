import { useEffect, useState } from "react";
import { api, urlDaApi } from "../api.js";
import { ACOES, CLASSES, MOTIVOS, STATUS, classe as rotuloClasse, data, numero, porcentagem } from "../rotulos.js";
import Selo from "./Selo.jsx";

function ImagemComCaixas({ src, deteccoes }) {
  const [mostrar, setMostrar] = useState(true);
  const [erro, setErro] = useState(false);
  const caixas = deteccoes ?? [];

  if (erro) return <div className="imagem-vazia muted">Imagem indisponível</div>;

  return (
    <figure className="figura">
      <div className="imagem-caixas">
        <img src={src} alt="Fotografia enviada pelo cidadão" onError={() => setErro(true)} />
        {mostrar &&
          caixas.map((d, i) => {
            const [x1, y1, x2, y2] = d.caixa;
            return (
              <div
                key={i}
                className={i === 0 ? "caixa principal" : "caixa"}
                style={{
                  left: `${x1 * 100}%`,
                  top: `${y1 * 100}%`,
                  width: `${(x2 - x1) * 100}%`,
                  height: `${(y2 - y1) * 100}%`,
                }}
              >
                {/* caixa encostada no topo: o rotulo vai para dentro dela */}
                <span className={y1 < 0.08 ? "dentro" : undefined}>
                  {CLASSES[d.classe]?.sigla ?? "?"} {porcentagem(d.confianca)}
                </span>
              </div>
            );
          })}
      </div>
      {caixas.length > 0 && (
        <figcaption>
          <label className="filtro-check pequeno">
            <input type="checkbox" checked={mostrar} onChange={(e) => setMostrar(e.target.checked)} />
            Mostrar {caixas.length} detecç{caixas.length === 1 ? "ão" : "ões"} do modelo
          </label>
        </figcaption>
      )}
    </figure>
  );
}

function descreverEvento(e) {
  const d = e.detalhe ?? {};
  if (e.acao === "criacao") {
    const gps = d.precisao_gps_m != null ? ` (GPS ±${numero(d.precisao_gps_m)} m)` : "";
    return `Reporte recebido pelo aplicativo${gps}`;
  }
  if (e.acao === "classificacao") {
    const modelo = d.classe_detectada
      ? `Modelo: ${rotuloClasse(d.classe_detectada)} com ${porcentagem(d.confianca)}`
      : "Modelo: nenhuma detecção";
    return `${modelo} → ${STATUS[d.para]?.rotulo ?? d.para} (${MOTIVOS[d.motivo] ?? d.motivo})`;
  }
  if (e.acao === "mudanca_status") {
    const obs = d.observacao ? ` · “${d.observacao}”` : "";
    const cls = d.para === "validada" && d.classe_validada ? ` como ${rotuloClasse(d.classe_validada)}` : "";
    return `${STATUS[d.de]?.rotulo ?? d.de} → ${STATUS[d.para]?.rotulo ?? d.para}${cls}${obs}`;
  }
  return e.acao;
}

export default function Detalhe({ id, aoFechar, aoAlterar, aoSelecionar }) {
  const [o, setO] = useState(null);
  const [erro, setErro] = useState("");
  const [observacao, setObservacao] = useState("");
  const [classeValidada, setClasseValidada] = useState("");
  const [raio, setRaio] = useState(100);
  const [enviando, setEnviando] = useState(false);

  useEffect(() => {
    let ativo = true;
    setO(null);
    setErro("");
    api(`/admin/ocorrencias/${id}`)
      .then((r) => {
        if (!ativo) return;
        setO(r);
        setClasseValidada(r.classe_final);
        setRaio(r.raio_m);
        setObservacao("");
      })
      .catch((e) => ativo && setErro(e.message));
    return () => {
      ativo = false;
    };
  }, [id]);

  useEffect(() => {
    const aoTeclar = (e) => e.key === "Escape" && aoFechar();
    window.addEventListener("keydown", aoTeclar);
    return () => window.removeEventListener("keydown", aoTeclar);
  }, [aoFechar]);

  async function aplicar(novo) {
    setEnviando(true);
    setErro("");
    try {
      const corpo = { status: novo, observacao: observacao.trim() || undefined };
      if (novo === "validada") {
        corpo.classe_validada = classeValidada;
        corpo.raio_m = Number(raio);
      }
      const r = await api(`/admin/ocorrencias/${id}/status`, { metodo: "PATCH", corpo });
      setO(r);
      setObservacao("");
      aoAlterar();
    } catch (e) {
      setErro(e.message);
    } finally {
      setEnviando(false);
    }
  }

  const podeValidar = o?.transicoes_permitidas.includes("validada");

  return (
    <div className="painel-lateral-fundo" onClick={aoFechar}>
      <aside
        className="painel-lateral"
        role="dialog"
        aria-modal="true"
        aria-label="Detalhe da ocorrência"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="lateral-topo">
          <div>
            <div className="mono grande">{o?.protocolo ?? "…"}</div>
            {o && <Selo status={o.status} />}
          </div>
          <button type="button" className="botao discreto" onClick={aoFechar} aria-label="Fechar">
            Fechar
          </button>
        </header>

        {erro && (
          <p className="erro" role="alert">
            {erro}
          </p>
        )}
        {!o && !erro && <p className="muted">Carregando…</p>}

        {o && (
          <div className="lateral-corpo">
            <ImagemComCaixas src={urlDaApi(o.imagem_url)} deteccoes={o.deteccoes} />

            <dl className="ficha">
              <dt>Informada pelo cidadão</dt>
              <dd>{rotuloClasse(o.classe_informada)}</dd>
              <dt>Detectada pelo modelo</dt>
              <dd>
                {o.classe_detectada
                  ? `${rotuloClasse(o.classe_detectada)} (${porcentagem(o.confianca)})`
                  : "Nenhuma detecção"}
                {o.classe_detectada && o.classe_detectada !== o.classe_informada && (
                  <span className="divergencia"> · diverge do cidadão</span>
                )}
              </dd>
              <dt>Validada pelo gestor</dt>
              <dd>{o.classe_validada ? rotuloClasse(o.classe_validada) : "–"}</dd>
              <dt>Localização</dt>
              <dd>
                <a
                  href={`https://www.openstreetmap.org/?mlat=${o.latitude}&mlon=${o.longitude}#map=18/${o.latitude}/${o.longitude}`}
                  target="_blank"
                  rel="noreferrer"
                >
                  {o.latitude.toFixed(6)}, {o.longitude.toFixed(6)}
                </a>
              </dd>
              <dt>Geocerca</dt>
              <dd>
                raio de {o.raio_m} m · {o.notificacoes_enviadas} alerta{o.notificacoes_enviadas === 1 ? "" : "s"}{" "}
                entregue{o.notificacoes_enviadas === 1 ? "" : "s"}
              </dd>
              <dt>Descrição</dt>
              <dd>{o.descricao || <span className="muted">sem descrição</span>}</dd>
              <dt>Modelo</dt>
              <dd className="mono pequeno">{o.modelo_versao ?? "–"}</dd>
              <dt>Reportada em</dt>
              <dd>{data(o.criado_em)}</dd>
            </dl>

            {o.possiveis_duplicatas.length > 0 && (
              <div className="aviso">
                <strong>Possível duplicata.</strong> Ocorrências da mesma classe muito próximas:
                <ul>
                  {o.possiveis_duplicatas.map((d) => (
                    <li key={d.id}>
                      <button type="button" className="link" onClick={() => aoSelecionar(d.id)}>
                        {d.protocolo}
                      </button>{" "}
                      a {numero(d.distancia_m)} m · {STATUS[d.status]?.rotulo}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {o.transicoes_permitidas.length > 0 && (
              <div className="acoes cartao">
                <h3>Ações</h3>
                {podeValidar && (
                  <div className="linha-campos">
                    <label className="campo">
                      <span>Classe ao validar</span>
                      <select value={classeValidada} onChange={(e) => setClasseValidada(e.target.value)}>
                        {Object.entries(CLASSES).map(([k, c]) => (
                          <option key={k} value={k}>
                            {c.rotulo}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label className="campo">
                      <span>Raio da geocerca (m)</span>
                      <input
                        type="number"
                        min={10}
                        max={1000}
                        step={10}
                        value={raio}
                        onChange={(e) => setRaio(e.target.value)}
                      />
                    </label>
                  </div>
                )}
                <label className="campo">
                  <span>Observação (opcional, fica no histórico)</span>
                  <textarea
                    rows={2}
                    maxLength={500}
                    value={observacao}
                    onChange={(e) => setObservacao(e.target.value)}
                  />
                </label>
                <div className="botoes">
                  {o.transicoes_permitidas.map((s) => (
                    <button
                      key={s}
                      type="button"
                      disabled={enviando}
                      className={
                        s === "validada" || s === "resolvida" || s === "em_atendimento"
                          ? "botao primario"
                          : s === "rejeitada"
                            ? "botao perigo"
                            : "botao"
                      }
                      onClick={() => aplicar(s)}
                    >
                      {ACOES[s] ?? s}
                    </button>
                  ))}
                </div>
              </div>
            )}

            <div>
              <h3>Histórico</h3>
              <ol className="linha-tempo">
                {o.auditoria.map((e, i) => (
                  <li key={i}>
                    <span className="muted pequeno">{data(e.criado_em)}</span>
                    <span>{descreverEvento(e)}</span>
                  </li>
                ))}
              </ol>
            </div>
          </div>
        )}
      </aside>
    </div>
  );
}
