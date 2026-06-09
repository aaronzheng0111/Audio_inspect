import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The front-end talks to the Django backend on :8000. We proxy /api during
// development so the browser sees a same-origin URL and we avoid CORS quirks.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});
