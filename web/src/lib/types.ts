/* eslint-disable @typescript-eslint/no-explicit-any */
// 계산 도구 결과는 src/assistant_tools.call_tool이 만든 JSON을 그대로 쓴다(화면에서 다시 계산하지 않는다).
export type Out = Record<string, any>
export type ToolName = "min_green" | "close_gap" | "simulate" | "compare_paths" | "h2_supply" | "abatement_curve"
export type Call = { name: string; input: Out; output: Out }
export type Hit = { name: ToolName; input: Out; output: Out }
export type Info = { ranges: Record<string, [number, number]>; defaults: Record<string, any>; h2_defaults?: Record<string, any>; plans: string[]; tools: Record<string, string> }
export const RESULT_TOOLS: ToolName[] = ["min_green", "close_gap", "simulate", "compare_paths", "h2_supply", "abatement_curve"]
export const isResult = (c: Call): c is Call & { name: ToolName } => (RESULT_TOOLS as string[]).includes(c.name) && c.output.status === "ok"
