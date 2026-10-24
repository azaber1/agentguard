"use client";

import { RunsTable } from "@/components/RunsTable";
import { Card, ErrorBanner, Loading, PageHeader } from "@/components/ui";
import { isActive } from "@/lib/format";
import { useApi } from "@/lib/hooks";
import type { Run } from "@/lib/types";

export default function RunsPage() {
  const { data, error } = useApi<Run[]>("/runs?limit=100", (d) => (d?.some((r) => isActive(r.status)) ? 2000 : null));
  return (
    <>
      <PageHeader title="Test runs" subtitle="Every execution of the scenario library, newest first." />
      <ErrorBanner message={error} />
      <Card>{data ? <RunsTable runs={data} /> : <Loading />}</Card>
    </>
  );
}
