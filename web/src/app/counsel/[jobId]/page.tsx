import type { Metadata } from "next";
import { Suspense } from "react";
import { AccountGate } from "@/components/counsel/Account";
import { CounselApp } from "@/components/counsel/CounselApp";

export const metadata: Metadata = {
  title: "Legal memo · Ain Copilot",
  description: "Verified legal risk memorandum with citation ledger, Virtual Bench and agent trace.",
};

export default function CounselJob({ params }: PageProps<"/counsel/[jobId]">) {
  return (
    <Suspense fallback={null}>
      {params.then(({ jobId }) => (
        <AccountGate>
          <CounselApp jobId={jobId} />
        </AccountGate>
      ))}
    </Suspense>
  );
}
