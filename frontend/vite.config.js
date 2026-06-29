import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The front-end talks to the Django backend on :9081 (see start.sh). We proxy
// /api during development so the browser sees a same-origin URL and we avoid
// CORS quirks. Large CSV paths (e.g. 400MB+ files) need a long proxy timeout.
const BACKEND_PORT = process.env.AUDIO_INSPECT_BACKEND_PORT || "9081";
const FRONTEND_PORT = Number(process.env.AUDIO_INSPECT_FRONTEND_PORT || "9173");

export default defineConfig({
  plugins: [react()],
  server: {
    port: FRONTEND_PORT,
    proxy: {
      "/api": {
        target: `http://127.0.0.1:${BACKEND_PORT}`,
        changeOrigin: true,
        timeout: 7_200_000,
        proxyTimeout: 7_200_000,
      },
    },
  },
});
