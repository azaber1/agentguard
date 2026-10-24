import type { TraceEvent } from "@/lib/types";
import { cx, Pill } from "./ui";

function Json({ value }: { value: unknown }) {
  return (
    <pre className="mt-1 max-h-64 overflow-auto whitespace-pre-wrap break-all rounded-md bg-surface-2 p-2 font-mono text-xs text-ink-2">
      {JSON.stringify(value, null, 2)}
    </pre>
  );
}

const LABEL: Record<TraceEvent["type"], string> = {
  user_message: "Customer",
  agent_message: "Agent",
  tool_call: "Tool call",
  tool_result: "Tool result",
  fault_injected: "Fault injected",
  system: "AgentGuard",
};

export function TraceViewer({ trace, flaggedSteps = [] }: { trace: TraceEvent[]; flaggedSteps?: number[] }) {
  const flagged = new Set(flaggedSteps);
  return (
    <ol className="space-y-2">
      {trace.map((e, i) => {
        const ok = e.type === "tool_result" ? Boolean(e.result?.ok) : null;
        return (
          <li
            key={i}
            className={cx(
              "rounded-lg border p-3 text-sm",
              flagged.has(e.step) && (e.type === "tool_call" || e.type === "agent_message") ? "border-critical" : "border-border",
              e.type === "user_message" && "bg-surface-2",
            )}
          >
            <div className="flex flex-wrap items-center gap-2 text-xs">
              <span className="tabular font-mono text-ink-3">#{e.step}</span>
              <span className="font-medium text-ink">{LABEL[e.type]}</span>
              {e.tool && <span className="font-mono text-ink-2">{e.tool}</span>}
              {ok === true && <Pill tone="good">ok</Pill>}
              {ok === false && <Pill tone="warning">{String(e.result?.error_code ?? "error")}</Pill>}
              {e.type === "fault_injected" && <Pill tone="warning">simulated fault</Pill>}
              {flagged.has(e.step) && (e.type === "tool_call" || e.type === "agent_message") && <Pill tone="critical">flagged</Pill>}
            </div>
            {e.content && e.type !== "fault_injected" && <p className="mt-1 whitespace-pre-wrap break-words text-ink">{e.content}</p>}
            {e.type === "fault_injected" && <p className="mt-1 text-ink-2">{e.content}</p>}
            {e.type === "tool_call" && <Json value={e.arguments} />}
            {e.type === "tool_result" && <Json value={e.result} />}
          </li>
        );
      })}
    </ol>
  );
}
