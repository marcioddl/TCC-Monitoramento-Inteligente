import { STATUS, grupoDoStatus } from "../rotulos.js";

// Status com ponto colorido + texto: a cor nunca carrega o significado sozinha
export default function Selo({ status }) {
  return (
    <span className={`selo selo-${grupoDoStatus(status)}`}>
      <span className="selo-ponto" aria-hidden="true" />
      {STATUS[status]?.rotulo ?? status}
    </span>
  );
}
