import { useEffect, useMemo, useRef, useState } from "react";
import L from "leaflet";
import { Circle, MapContainer, Marker, TileLayer, Tooltip, useMap } from "react-leaflet";
import { api } from "../api.js";
import { CLASSES, GRUPOS, STATUS, classe as rotuloClasse, data, grupoDoStatus } from "../rotulos.js";

const TERESINA = [-5.0892, -42.8016];
const ATUALIZAR_A_CADA_MS = 30_000;
const PERIODOS = [
  { dias: 7, rotulo: "Últimos 7 dias" },
  { dias: 30, rotulo: "Últimos 30 dias" },
  { dias: 90, rotulo: "Últimos 90 dias" },
  { dias: 0, rotulo: "Todo o período" },
];

const icones = new Map();
function icone(grupo, sigla) {
  const chave = `${grupo}-${sigla}`;
  if (!icones.has(chave)) {
    icones.set(
      chave,
      L.divIcon({
        className: `marcador marcador-${grupo}`,
        html: `<span>${sigla}</span>`,
        iconSize: [26, 26],
        iconAnchor: [13, 13],
        tooltipAnchor: [0, -14],
      }),
    );
  }
  return icones.get(chave);
}

function cor(variavel) {
  return getComputedStyle(document.documentElement).getPropertyValue(variavel).trim() || "#2a78d6";
}

function AjustarVisao({ pontos }) {
  const mapa = useMap();
  const ajustado = useRef(false);
  useEffect(() => {
    if (ajustado.current || pontos.length === 0) return;
    ajustado.current = true;
    if (pontos.length === 1) mapa.setView(pontos[0], 16);
    else mapa.fitBounds(L.latLngBounds(pontos), { padding: [40, 40], maxZoom: 16 });
  }, [mapa, pontos]);
  return null;
}

function CamadaCalor({ pontos }) {
  const mapa = useMap();
  useEffect(() => {
    let camada;
    let cancelado = false;
    // o plugin leaflet.heat procura o Leaflet no objeto global
    window.L = L;
    import("leaflet.heat").then(() => {
      if (cancelado) return;
      camada = L.heatLayer(
        pontos.map((p) => [p[0], p[1], 1]),
        {
          radius: 28,
          blur: 22,
          minOpacity: 0.25,
          // rampa sequencial de um so matiz (azul), do claro ao escuro
          gradient: { 0.2: "#b7d3f6", 0.45: "#6da7ec", 0.7: "#256abf", 1.0: "#0d366b" },
        },
      ).addTo(mapa);
    });
    return () => {
      cancelado = true;
      if (camada) mapa.removeLayer(camada);
    };
  }, [mapa, pontos]);
  return null;
}

export default function Mapa({ versao, aoSelecionar }) {
  const [grupos, setGrupos] = useState({ aguardando: true, ativa: true, encerrada: false });
  const [classe, setClasse] = useState("");
  const [dias, setDias] = useState(30);
  const [geocercas, setGeocercas] = useState(true);
  const [calor, setCalor] = useState(false);
  const [itens, setItens] = useState([]);
  const [total, setTotal] = useState(0);
  const [atualizadoEm, setAtualizadoEm] = useState(null);
  const [erro, setErro] = useState("");
  const [carregando, setCarregando] = useState(true);

  const statusSelecionados = useMemo(
    () => Object.entries(grupos).filter(([, on]) => on).flatMap(([g]) => GRUPOS[g].status),
    [grupos],
  );

  useEffect(() => {
    let ativo = true;
    async function carregar() {
      if (statusSelecionados.length === 0) {
        setItens([]);
        setTotal(0);
        setCarregando(false);
        return;
      }
      try {
        const desde = dias ? new Date(Date.now() - dias * 86_400_000).toISOString() : undefined;
        const r = await api("/admin/ocorrencias", {
          params: { status: statusSelecionados, classe, desde, limite: 2000 },
        });
        if (!ativo) return;
        setItens(r.itens);
        setTotal(r.total);
        setAtualizadoEm(new Date());
        setErro("");
      } catch (e) {
        if (ativo) setErro(e.message);
      } finally {
        if (ativo) setCarregando(false);
      }
    }
    carregar();
    const relogio = setInterval(carregar, ATUALIZAR_A_CADA_MS);
    return () => {
      ativo = false;
      clearInterval(relogio);
    };
  }, [statusSelecionados, classe, dias, versao]);

  const pontos = useMemo(() => itens.map((o) => [o.latitude, o.longitude]), [itens]);
  const corAtiva = cor("--grupo-ativa");

  return (
    <section className="visao-mapa">
      <div className="filtros" role="group" aria-label="Filtros do mapa">
        {Object.entries(GRUPOS).map(([chave, g]) => (
          <label key={chave} className="filtro-check">
            <input
              type="checkbox"
              checked={grupos[chave]}
              onChange={(e) => setGrupos({ ...grupos, [chave]: e.target.checked })}
            />
            <span className={`chave-cor chave-${chave}`} aria-hidden="true" />
            {g.rotulo}
          </label>
        ))}
        <select value={classe} onChange={(e) => setClasse(e.target.value)} aria-label="Classe">
          <option value="">Todas as classes</option>
          {Object.entries(CLASSES).map(([k, c]) => (
            <option key={k} value={k}>
              {c.rotulo}
            </option>
          ))}
        </select>
        <select value={dias} onChange={(e) => setDias(Number(e.target.value))} aria-label="Período">
          {PERIODOS.map((p) => (
            <option key={p.dias} value={p.dias}>
              {p.rotulo}
            </option>
          ))}
        </select>
        <label className="filtro-check">
          <input type="checkbox" checked={geocercas} onChange={(e) => setGeocercas(e.target.checked)} />
          Geocercas
        </label>
        <label className="filtro-check">
          <input type="checkbox" checked={calor} onChange={(e) => setCalor(e.target.checked)} />
          Mapa de calor
        </label>
        <span className="filtros-info muted">
          {carregando
            ? "Carregando…"
            : `${itens.length}${total > itens.length ? ` de ${total}` : ""} no mapa`}
          {atualizadoEm && ` · atualizado às ${atualizadoEm.toLocaleTimeString("pt-BR")}`}
        </span>
      </div>
      {erro && (
        <p className="erro" role="alert">
          {erro}
        </p>
      )}

      <div className="mapa-moldura">
        <MapContainer center={TERESINA} zoom={13} className="mapa" scrollWheelZoom>
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          <AjustarVisao pontos={pontos} />
          {calor && pontos.length > 0 && <CamadaCalor pontos={pontos} />}

          {!calor &&
            geocercas &&
            itens
              .filter((o) => grupoDoStatus(o.status) === "ativa")
              .map((o) => (
                <Circle
                  key={`cerca-${o.id}`}
                  center={[o.latitude, o.longitude]}
                  radius={o.raio_m}
                  interactive={false}
                  pathOptions={{ color: corAtiva, weight: 1, fillColor: corAtiva, fillOpacity: 0.08 }}
                />
              ))}

          {!calor &&
            itens.map((o) => (
              <Marker
                key={o.id}
                position={[o.latitude, o.longitude]}
                icon={icone(grupoDoStatus(o.status), CLASSES[o.classe_final]?.sigla ?? "?")}
                eventHandlers={{ click: () => aoSelecionar(o.id) }}
                keyboard
                title={`${o.protocolo}: ${rotuloClasse(o.classe_final)}`}
              >
                <Tooltip direction="top">
                  <strong>{o.protocolo}</strong>
                  <br />
                  {rotuloClasse(o.classe_final)} · {STATUS[o.status]?.rotulo}
                  <br />
                  <span className="muted">{data(o.criado_em)}</span>
                </Tooltip>
              </Marker>
            ))}
        </MapContainer>

        <div className="legenda-mapa" aria-label="Legenda">
          {calor ? (
            <div className="legenda-calor">
              <span>Menos</span>
              <span className="rampa" aria-hidden="true" />
              <span>Mais ocorrências</span>
            </div>
          ) : (
            <>
              {Object.entries(GRUPOS).map(([chave, g]) => (
                <div key={chave} className="legenda-item">
                  <span className={`marcador-legenda marcador-${chave}`} aria-hidden="true" />
                  {g.rotulo}
                </div>
              ))}
              <div className="legenda-item muted">B buraco · C calçada</div>
              {geocercas && <div className="legenda-item muted">Círculo: raio de alerta da geocerca</div>}
            </>
          )}
        </div>
      </div>
    </section>
  );
}
