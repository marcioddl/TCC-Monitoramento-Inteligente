import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// O painel e servido pelo proprio FastAPI em /painel (pasta dist/).
// Em desenvolvimento (npm run dev), as chamadas a API sao repassadas ao
// uvicorn na porta 8000, entao o painel usa sempre caminhos relativos.
const API = process.env.MIIU_API ?? "http://localhost:8000";
const rotasDaApi = ["/admin", "/ocorrencias", "/health", "/dispositivos", "/geofence"];

export default defineConfig({
  base: "/painel/",
  plugins: [react()],
  server: {
    port: 5173,
    proxy: Object.fromEntries(rotasDaApi.map((rota) => [rota, { target: API, changeOrigin: true }])),
  },
  build: {
    outDir: "dist",
    chunkSizeWarningLimit: 800,
  },
});
