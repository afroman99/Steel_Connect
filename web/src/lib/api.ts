import type { Info, Out } from "./types"

export const post = (url: string, body: unknown): Promise<Out> =>
  fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }).then((r) => r.json())
export const calc = (tool: string, args: Out) => post("/api/calc", { tool, args })
export const getInfo = (): Promise<Info> => fetch("/api/tools").then((r) => r.json())
export const getStatus = (): Promise<{ llm: string | null }> => fetch("/api/status").then((r) => r.json())
