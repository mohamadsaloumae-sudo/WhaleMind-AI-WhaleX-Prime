import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

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
  build: {
    outDir: "dist",
    // 📦 تقسيم الحزمة: المكتبات في ملفّات ببصمات ثابتة، فتحديث كودنا
    //    لا يُبطل مخزون React ولا الأيقونات عند المستخدم.
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes("node_modules")) return;
          if (id.includes("recharts") || id.includes("d3-")) return "charts";
          if (id.includes("lucide-react")) return "icons";
          if (id.includes("react-router")) return "router";
          if (id.includes("/react/") || id.includes("react-dom")
              || id.includes("scheduler")) return "react";
          return "vendor";
        },
      },
    },
    chunkSizeWarningLimit: 700,
  },
});
