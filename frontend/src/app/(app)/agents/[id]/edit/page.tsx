"use client";

import { use } from "react";
import { AgentForm } from "@/components/AgentForm";
import { ErrorBanner, Loading, PageHeader } from "@/components/ui";
import { useApi } from "@/lib/hooks";
import type { Agent } from "@/lib/types";

export default function EditAgentPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { data, error } = useApi<Agent>(`/agents/${id}`);
  if (error) return <ErrorBanner message={error} />;
  if (!data) return <Loading />;
  return (
    <>
      <PageHeader title={`Edit ${data.name}`} />
      <AgentForm agent={data} />
    </>
  );
}
