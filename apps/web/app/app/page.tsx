import type { Metadata } from "next";
import { NewJobForm } from "./new-job-form";

export const metadata: Metadata = {
  title: "Novo job — EVA",
};

export default function AppHomePage() {
  return (
    <main className="flex min-h-screen items-center justify-center px-6">
      <NewJobForm />
    </main>
  );
}
