import path from "node:path"
import tailwindcss from "@tailwindcss/vite"
import react from "@vitejs/plugin-react"
import { defineConfig } from "vite"

// 개발 중에는 /api를 파이썬 서버(python3 -m src.web, 8000번)로 넘긴다. 빌드 결과(web/dist)는 그 서버가 그대로 내준다.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: { alias: { "@": path.resolve(__dirname, "./src") } },
  server: { proxy: { "/api": "http://127.0.0.1:8000" } },
})
