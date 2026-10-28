import { useState } from "react";
import { sessao } from "../api.js";

export default function Login({ aoEntrar }) {
  const [senha, setSenha] = useState("");
  const [erro, setErro] = useState("");
  const [enviando, setEnviando] = useState(false);

  async function enviar(evento) {
    evento.preventDefault();
    setEnviando(true);
    setErro("");
    try {
      await sessao.entrar(senha);
      aoEntrar();
    } catch (e) {
      setErro(e.message);
    } finally {
      setEnviando(false);
    }
  }

  return (
    <div className="login">
      <form className="cartao login-cartao" onSubmit={enviar}>
        <h1>MIIU</h1>
        <p className="secundario">
          Monitoramento Inteligente de Infraestrutura Urbana
          <br />
          Painel de gestão
        </p>
        <label className="campo">
          <span>Senha do painel</span>
          <input
            type="password"
            autoFocus
            autoComplete="current-password"
            value={senha}
            onChange={(e) => setSenha(e.target.value)}
            required
          />
        </label>
        {erro && (
          <p className="erro" role="alert">
            {erro}
          </p>
        )}
        <button type="submit" className="botao primario" disabled={enviando || !senha}>
          {enviando ? "Entrando…" : "Entrar"}
        </button>
        <p className="muted pequeno">A senha é a ADMIN_SENHA definida no arquivo .env do backend.</p>
      </form>
    </div>
  );
}
