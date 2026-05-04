import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/run-pipeline": "http://127.0.0.1:8000",
      "/run-phase": "http://127.0.0.1:8000",
      "/status": "http://127.0.0.1:8000",
      "/result": "http://127.0.0.1:8000",
      "/events": "http://127.0.0.1:8000",
      "/media": "http://127.0.0.1:8000",
      "/health": "http://127.0.0.1:8000"
    }
  }
});
