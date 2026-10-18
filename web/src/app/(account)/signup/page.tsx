import type { Metadata } from "next";
import { Suspense } from "react";
import { AuthForm } from "@/components/counsel/AuthForm";

export const metadata: Metadata = {
  title: "Create account · Ain Copilot",
  description: "Create an account to keep your contract analyses private and available on any device.",
};

export default function SignupPage() {
  return (
    <Suspense fallback={null}>
      <AuthForm mode="signup" />
    </Suspense>
  );
}
