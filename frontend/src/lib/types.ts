export type Severity = "critical" | "high" | "medium" | "low";
export type ResultStatus = "passed" | "failed" | "error";
export type RunStatus = "queued" | "running" | "completed" | "failed";

export interface User {
  id: string;
  email: string;
  full_name: string;
  role: string;
  organization: { id: string; name: string };
}

export interface AgentPolicy {
  max_refund_amount: number;
  require_identity_verification: boolean;
  max_tool_calls_per_session: number;
  max_identical_tool_calls: number;
}

export interface RunBrief {
  id: string;
  status: RunStatus;
  reliability_score: number | null;
  passed: number;
  failed: number;
  errored: number;
  total: number;
  created_at: string;
  completed_at: string | null;
}

export interface Agent {
  id: string;
  name: string;
  description: string;
  provider: "simulated" | "http";
  provider_config: { profile?: string; endpoint_url?: string; timeout_seconds?: number };
  system_prompt: string;
  tools: string[];
  allowed_tools: string[];
  policy: AgentPolicy;
  has_auth_token: boolean;
  created_at: string;
  updated_at: string;
  latest_run: RunBrief | null;
}

export interface Tool {
  name: string;
  description: string;
  category: string;
  parameters: Record<string, unknown>;
}

export interface Profile {
  id: string;
  label: string;
  description: string;
}

export interface ScenarioSummary {
  id: string;
  name: string;
  category: string;
  category_label: string;
  severity: Severity;
  description: string;
  tags: string[];
}

export interface ScenarioDetail extends ScenarioSummary {
  user_turns: string[];
  persona: { customer_id: string | null; description: string };
  expectations: {
    required_tools: string[];
    forbidden_tools: string[];
    max_tool_calls: number | null;
    response_must_match: string[];
    response_must_not_match: string[];
  };
  faults: { tool: string; mode: string; times?: number | null }[];
  has_injection: boolean;
}

export interface Finding {
  id: string;
  rule_id: string;
  title: string;
  severity: Severity;
  category: string;
  owasp_ref: string;
  source: "policy" | "expectation" | "execution";
  explanation: string;
  recommendation: string;
  evidence: Record<string, unknown>;
}

export interface ExpectationCheck {
  description: string;
  expected: string;
  actual: string;
  passed: boolean;
}

export interface ResultSummary {
  id: string;
  scenario_id: string;
  scenario_name: string;
  category: string;
  severity: Severity;
  status: ResultStatus;
  score: number;
  metrics: Record<string, number>;
  error: string | null;
  expectations: ExpectationCheck[];
  findings: Finding[];
}

export interface TraceEvent {
  step: number;
  type: "user_message" | "agent_message" | "tool_call" | "tool_result" | "fault_injected" | "system";
  content?: string;
  tool?: string;
  arguments?: Record<string, unknown>;
  result?: Record<string, unknown>;
  call_id?: string;
}

export interface ResultDetail extends ResultSummary {
  trace: TraceEvent[];
  sandbox_effects: Record<string, unknown[]>;
}

export interface Run {
  id: string;
  agent_id: string;
  agent_name: string;
  status: RunStatus;
  scenario_ids: string[];
  total: number;
  passed: number;
  failed: number;
  errored: number;
  reliability_score: number | null;
  critical_findings: number;
  error: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
}

export interface RunDetail extends Run {
  agent_snapshot: Record<string, unknown> & { policy: AgentPolicy; tools: string[]; allowed_tools: string[] };
  results: ResultSummary[];
  disclaimer: string;
}

export interface Dashboard {
  totals: {
    runs: number;
    agents: number;
    tests_executed: number;
    passed: number;
    failed: number;
    errored: number;
    pass_rate: number | null;
  };
  reliability_score: number | null;
  security_violations: {
    total: number;
    by_severity: Partial<Record<Severity, number>>;
    by_category: Record<string, number>;
    top_rules: { rule_id: string; title: string; count: number }[];
  };
  category_results: { category: string; label: string; total: number; passed: number }[];
  agents: {
    id: string;
    name: string;
    provider: string;
    latest_run: {
      id: string;
      reliability_score: number | null;
      passed: number;
      total: number;
      critical_findings: number;
      completed_at: string;
    } | null;
  }[];
  recent_runs: (Run & { agent_name: string })[];
  disclaimer: string;
}
