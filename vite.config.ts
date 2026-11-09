import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// Set by `tauri android dev` / `tauri ios dev` so the device can reach the dev server.
const host = process.env.TAURI_DEV_HOST;

export default defineConfig({
  plugins: [react(), tailwindcss()],
  clearScreen: false,
  envPrefix: ["VITE_", "TAURI_ENV_"],
  server: {
    port: 1420,
    strictPort: true,
    host: host || false,
    hmr: host ? { protocol: "ws", host, port: 1421 } : undefined,
    watch: { ignored: ["**/src-tauri/**"] },
  },
  // ffmpeg.wasm spawns its own module worker; pre-bundling breaks its worker URL.
  optimizeDeps: { exclude: ["@ffmpeg/ffmpeg"] },
  worker: { format: "es" },
  build: { target: "es2022", outDir: "dist" },
});
