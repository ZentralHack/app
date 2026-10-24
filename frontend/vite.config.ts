import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// The backend binds to 127.0.0.1 only; "localhost" would try IPv6 first and stall on Windows.
const BACKEND = "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: { "/api": { target: BACKEND, changeOrigin: true } },
  },
});
