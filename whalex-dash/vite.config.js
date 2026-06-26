import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// التطوير: يمرّر طلبات /api إلى الباك-إند FastAPI على 8000
export default defineConfig({
  plugins: [react()],
  server: {
    host: "0.0.0.0",
    port: 5173,
    proxy: {
      "/api": { target: "http://localhost:8000", changeOrigin: true },
      "/ws": { target: "ws://localhost:8000", ws: true },
    },
  },
  build: { outDir: "dist" },
});
