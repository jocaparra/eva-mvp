import type { Metadata } from "next";
import { SignupForm } from "./signup-form";

export const metadata: Metadata = {
  title: "Criar conta — EVA",
};

export default function SignupPage() {
  return <SignupForm />;
}
