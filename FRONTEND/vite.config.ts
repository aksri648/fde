import { defineConfig } from "vite";
import solidPlugin from "vite-plugin-solid";

export default defineConfig({
  plugins: [solidPlugin()],
  server: {
    port: 5173,
    proxy: {
      "/v1/sessions": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
      "/v1": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
  build: {
    target: "es2020",
  },
});
