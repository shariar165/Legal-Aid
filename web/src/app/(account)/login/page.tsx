import type { Metadata } from "next";
import { Suspense } from "react";
import { AuthForm } from "@/components/counsel/AuthForm";

export const metadata: Metadata = {
  title: "Sign in · Ain Copilot",
  description: "Sign in to open your saved analyses and Counsel mode.",
};

export default function LoginPage() {
  return (
    <Suspense fallback={null}>
      <AuthForm mode="login" />
    </Suspense>
  );
}
