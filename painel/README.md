# MIIU · Painel de gestão (React + Leaflet)

O painel já vai compilado em `dist/` e é servido pelo próprio backend:
com o uvicorn rodando, abra **http://localhost:8000/painel** e entre com a
`ADMIN_SENHA` do `.env`. Não é preciso instalar o Node para usar.

## Visões

- **Mapa**: ocorrências coloridas pela situação (laranja = aguardando gestão,
  azul = ativa e gerando alertas, cinza = encerrada), com a letra da classe
  (B buraco, C calçada) e o círculo da geocerca. Filtros por situação, classe
  e período, e mapa de calor da concentração de ocorrências. Atualiza a cada
  30 s.
- **Ocorrências**: lista filtrável (abre em "Aguardando gestão", que é a fila
  de triagem), busca por protocolo ou descrição e exportação em CSV.
- **Detalhe** (ao clicar numa ocorrência): foto com as caixas detectadas pelo
  modelo, classe do cidadão × modelo × gestor, possíveis duplicatas a menos de
  30 m, ações permitidas pela máquina de estados (validar escolhendo classe e
  raio da geocerca, rejeitar, iniciar atendimento, resolver) com observação, e
  o histórico completo.
- **Indicadores**: total, fila, taxa de automação, concordância modelo ×
  gestor e cidadão × gestor, tempos médios até a triagem e até a resolução,
  alertas entregues e distância média, aparelhos ativos, reportes por dia e
  distribuição por status e por classe. Cada gráfico tem a opção "Ver tabela".

## Desenvolvimento

Só é preciso para alterar o painel. Requer Node 18 ou mais novo.

```powershell
cd C:\Users\"Marcio Felipe"\miiu\painel
npm install
npm run dev        # http://localhost:5173/painel/, recarrega ao salvar
npm run build      # gera dist/, que o backend serve em /painel
```

Em modo de desenvolvimento, as chamadas à API são repassadas ao uvicorn na
porta 8000 (veja `vite.config.js`).
