import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { api } from "../api.js";
import { CLASSES, GRUPOS, ORDEM_STATUS, STATUS, horas, numero, porcentagem } from "../rotulos.js";

function useLargura() {
  const ref = useRef(null);
  const [largura, setLargura] = useState(0);
  useLayoutEffect(() => {
    if (!ref.current) return;
    const observador = new ResizeObserver(([entrada]) => setLargura(entrada.contentRect.width));
    observador.observe(ref.current);
    return () => observador.disconnect();
  }, []);
  return [ref, largura];
}

function tetoRedondo(valor) {
  if (valor <= 5) return 5;
  const ordem = 10 ** Math.floor(Math.log10(valor));
  for (const m of [1, 2, 5, 10]) if (valor <= m * ordem) return m * ordem;
  return 10 * ordem;
}

function colunaArredondada(x, y, largura, base) {
  const altura = base - y;
  const r = Math.min(4, largura / 2, altura);
  if (altura <= 0) return "";
  return `M${x},${base} V${y + r} Q${x},${y} ${x + r},${y} H${x + largura - r} Q${x + largura},${y} ${x + largura},${y + r} V${base} Z`;
}

function ReportesPorDia({ dados }) {
  const [ref, largura] = useLargura();
  const [foco, setFoco] = useState(null);
  const altura = 200;
  const m = { topo: 18, dir: 8, base: 26, esq: 34 };
  const larguraPlot = Math.max(largura - m.esq - m.dir, 10);
  const alturaPlot = altura - m.topo - m.base;
  const maximo = Math.max(...dados.map((d) => d.total), 0);
  const teto = tetoRedondo(maximo);
  const faixa = larguraPlot / Math.max(dados.length, 1);
  const larguraBarra = Math.max(Math.min(24, faixa - 2), 2);
  const y = (v) => m.topo + alturaPlot - (v / teto) * alturaPlot;
  const passoRotulo = Math.max(1, Math.ceil(dados.length / Math.max(larguraPlot / 48, 1)));
  const indiceMaximo = dados.findIndex((d) => d.total === maximo && maximo > 0);
  const rotuloDia = (iso) => `${iso.slice(8, 10)}/${iso.slice(5, 7)}`;

  return (
    <div className="grafico" ref={ref}>
      {largura > 0 && (
        <svg width={largura} height={altura} role="img" aria-label="Reportes por dia">
          {[0, teto / 2, teto].map((t) => (
            <g key={t}>
              <line x1={m.esq} x2={largura - m.dir} y1={y(t)} y2={y(t)} className={t === 0 ? "eixo" : "grade"} />
              <text x={m.esq - 6} y={y(t)} className="tick" textAnchor="end" dominantBaseline="middle">
                {numero(t)}
              </text>
            </g>
          ))}
          {dados.map((d, i) => {
            const x = m.esq + i * faixa + (faixa - larguraBarra) / 2;
            return (
              <g key={d.dia}>
                <path d={colunaArredondada(x, y(d.total), larguraBarra, y(0))} className="barra" />
                {i === indiceMaximo && (
                  <text x={x + larguraBarra / 2} y={y(d.total) - 5} className="valor" textAnchor="middle">
                    {d.total}
                  </text>
                )}
                {i % passoRotulo === 0 && (
                  <text x={x + larguraBarra / 2} y={altura - 8} className="tick" textAnchor="middle">
                    {rotuloDia(d.dia)}
                  </text>
                )}
                <rect
                  x={m.esq + i * faixa}
                  y={m.topo}
                  width={faixa}
                  height={alturaPlot}
                  className="alvo"
                  onMouseEnter={() => setFoco(i)}
                  onMouseLeave={() => setFoco(null)}
                />
              </g>
            );
          })}
        </svg>
      )}
      {foco !== null && dados[foco] && (
        <div
          className="dica"
          style={{
            left: Math.min(Math.max(m.esq + foco * faixa + faixa / 2, 60), largura - 60),
            top: y(dados[foco].total) - 8,
          }}
        >
          <strong>{dados[foco].total}</strong> reporte{dados[foco].total === 1 ? "" : "s"}
          <br />
          <span className="muted">{new Date(`${dados[foco].dia}T12:00:00`).toLocaleDateString("pt-BR")}</span>
        </div>
      )}
    </div>
  );
}

function BarrasHorizontais({ itens }) {
  const maximo = Math.max(...itens.map((i) => i.valor), 1);
  return (
    <div className="barras-h">
      {itens.map((item) => (
        <div key={item.rotulo} className="barra-h-linha">
          <span className="barra-h-rotulo">{item.rotulo}</span>
          <span className="barra-h-trilho">
            {item.valor > 0 && <span className="barra-h" style={{ width: `${(item.valor / maximo) * 100}%` }} />}
            <span className="barra-h-valor">{numero(item.valor)}</span>
          </span>
        </div>
      ))}
    </div>
  );
}

function TabelaSimples({ colunas, linhas }) {
  return (
    <table className="tabela compacta">
      <thead>
        <tr>
          {colunas.map((c, i) => (
            <th key={c} className={i > 0 ? "num" : undefined}>
              {c}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {linhas.map((l) => (
          <tr key={l[0]}>
            {l.map((v, i) => (
              <td key={i} className={i > 0 ? "num" : undefined}>
                {v}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function Cartao({ titulo, subtitulo, tabela, children }) {
  const [verTabela, setVerTabela] = useState(false);
  return (
    <section className="cartao grafico-cartao">
      <header className="grafico-topo">
        <div>
          <h3>{titulo}</h3>
          {subtitulo && <p className="muted pequeno">{subtitulo}</p>}
        </div>
        <button type="button" className="botao discreto pequeno" onClick={() => setVerTabela((v) => !v)}>
          {verTabela ? "Ver gráfico" : "Ver tabela"}
        </button>
      </header>
      {verTabela ? tabela : children}
    </section>
  );
}

function Tile({ rotulo, valor, detalhe }) {
  return (
    <div className="tile">
      <span className="tile-rotulo">{rotulo}</span>
      <span className="tile-valor">{valor}</span>
      {detalhe && <span className="tile-detalhe muted">{detalhe}</span>}
    </div>
  );
}

export default function Indicadores({ versao }) {
  const [dias, setDias] = useState(30);
  const [e, setE] = useState(null);
  const [erro, setErro] = useState("");

  useEffect(() => {
    let ativo = true;
    api("/admin/estatisticas", { params: { dias } })
      .then((r) => ativo && (setE(r), setErro("")))
      .catch((x) => ativo && setErro(x.message));
    return () => {
      ativo = false;
    };
  }, [dias, versao]);

  if (erro)
    return (
      <p className="erro" role="alert">
        {erro}
      </p>
    );
  if (!e) return <p className="muted">Carregando…</p>;

  const aguardando = GRUPOS.aguardando.status.reduce((s, k) => s + (e.por_status[k] ?? 0), 0);
  const porStatus = ORDEM_STATUS.map((s) => ({ rotulo: STATUS[s].rotulo, valor: e.por_status[s] ?? 0 }));
  const porClasse = Object.entries(CLASSES).map(([k, c]) => ({ rotulo: c.rotulo, valor: e.por_classe[k] ?? 0 }));
  const canais = Object.entries(e.notificacoes_por_canal)
    .map(([k, v]) => `${v} ${k === "fcm" ? "por push" : "no app"}`)
    .join(" · ");

  return (
    <section className="visao-indicadores">
      <div className="filtros">
        <select value={dias} onChange={(x) => setDias(Number(x.target.value))} aria-label="Período da série diária">
          <option value={30}>Série diária: últimos 30 dias</option>
          <option value={90}>Série diária: últimos 90 dias</option>
          <option value={180}>Série diária: últimos 180 dias</option>
        </select>
        <span className="muted pequeno">Os demais indicadores consideram todo o período.</span>
      </div>

      <div className="tiles">
        <Tile rotulo="Ocorrências registradas" valor={numero(e.total)} />
        <Tile rotulo="Aguardando gestão" valor={numero(aguardando)} detalhe="recebidas, classificadas e em triagem" />
        <Tile
          rotulo="Classificadas sem triagem humana"
          valor={porcentagem(e.taxa_automacao)}
          detalhe="taxa de automação do modelo"
        />
        <Tile
          rotulo="Concordância modelo × gestor"
          valor={porcentagem(e.concordancia_modelo)}
          detalhe={`em ${e.validadas_avaliadas} validadas`}
        />
        <Tile rotulo="Concordância cidadão × gestor" valor={porcentagem(e.concordancia_cidadao)} />
        <Tile rotulo="Tempo médio até a triagem" valor={horas(e.tempo_medio_triagem_h)} />
        <Tile rotulo="Tempo médio até a resolução" valor={horas(e.tempo_medio_resolucao_h)} />
        <Tile
          rotulo="Alertas de proximidade entregues"
          valor={numero(e.notificacoes_enviadas)}
          detalhe={
            e.distancia_media_alerta_m != null
              ? `distância média ${numero(e.distancia_media_alerta_m)} m${canais ? ` · ${canais}` : ""}`
              : null
          }
        />
        <Tile rotulo="Aparelhos ativos (7 dias)" valor={numero(e.dispositivos_ativos_7d)} />
      </div>

      <Cartao
        titulo="Reportes por dia"
        subtitulo={`Últimos ${dias} dias, horário de Teresina`}
        tabela={
          <TabelaSimples
            colunas={["Dia", "Reportes"]}
            linhas={e.por_dia.map((d) => [new Date(`${d.dia}T12:00:00`).toLocaleDateString("pt-BR"), d.total])}
          />
        }
      >
        <ReportesPorDia dados={e.por_dia} />
      </Cartao>

      <div className="grade-2">
        <Cartao
          titulo="Ocorrências por status"
          tabela={<TabelaSimples colunas={["Status", "Ocorrências"]} linhas={porStatus.map((i) => [i.rotulo, i.valor])} />}
        >
          <BarrasHorizontais itens={porStatus} />
        </Cartao>
        <Cartao
          titulo="Ocorrências por classe"
          subtitulo="Classe validada pelo gestor ou, antes disso, a do modelo"
          tabela={<TabelaSimples colunas={["Classe", "Ocorrências"]} linhas={porClasse.map((i) => [i.rotulo, i.valor])} />}
        >
          <BarrasHorizontais itens={porClasse} />
        </Cartao>
      </div>
    </section>
  );
}
