import { AgentForm } from "@/components/AgentForm";
import { PageHeader } from "@/components/ui";

export default function NewAgentPage() {
  return (
    <>
      <PageHeader title="Register agent" subtitle="Describe the agent under test and what it is allowed to do." />
      <AgentForm />
    </>
  );
}
