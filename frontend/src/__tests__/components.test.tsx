import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { TraceViewer } from "@/components/TraceViewer";
import { Disclaimer, Meter, ScoreBadge, SeverityBadge, StatusBadge } from "@/components/ui";

describe("badges", () => {
  it("always pair status colour with a text label", () => {
    render(
      <>
        <StatusBadge status="failed" />
        <SeverityBadge severity="critical" />
        <ScoreBadge score={42} />
      </>,
    );
    expect(screen.getByText("Failed")).toBeInTheDocument();
    expect(screen.getByText("Critical")).toBeInTheDocument();
    expect(screen.getByText("42")).toBeInTheDocument();
    expect(screen.getByText("At risk")).toBeInTheDocument();
  });

  it("shows no-data state for missing scores", () => {
    render(<ScoreBadge score={null} />);
    expect(screen.getByText("No data")).toBeInTheDocument();
  });
});

it("meter exposes its value accessibly", () => {
  render(<Meter value={3} max={4} label="Prompt injection pass rate" />);
  const meter = screen.getByRole("meter", { name: "Prompt injection pass rate" });
  expect(meter).toHaveAttribute("aria-valuenow", "3");
  expect(meter).toHaveAttribute("aria-valuemax", "4");
});

it("disclaimer states that tests are not a guarantee", () => {
  render(<Disclaimer />);
  expect(screen.getByText(/not a guarantee/i)).toBeInTheDocument();
});

it("trace viewer renders each event and marks flagged steps", () => {
  render(
    <TraceViewer
      flaggedSteps={[2]}
      trace={[
        { step: 1, type: "user_message", content: "Refund ORD-1003" },
        { step: 2, type: "tool_call", tool: "issue_refund", arguments: { amount: 899 } },
        { step: 2, type: "tool_result", tool: "issue_refund", result: { ok: false, error_code: "timeout" } },
        { step: 3, type: "agent_message", content: "Done!" },
      ]}
    />,
  );
  expect(screen.getByText("Refund ORD-1003")).toBeInTheDocument();
  expect(screen.getByText(/"amount": 899/)).toBeInTheDocument();
  expect(screen.getAllByText("timeout").length).toBeGreaterThan(0);
  expect(screen.getByText("flagged")).toBeInTheDocument();
  expect(screen.getByText("Done!")).toBeInTheDocument();
});
