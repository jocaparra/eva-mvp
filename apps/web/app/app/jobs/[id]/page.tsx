import type { Metadata } from "next";
import { JobDetail } from "./job-detail";

export const metadata: Metadata = {
  title: "Job — EVA",
};

export default async function JobDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return (
    <main className="mx-auto max-w-3xl px-8 py-12">
      <JobDetail jobId={id} />
    </main>
  );
}
