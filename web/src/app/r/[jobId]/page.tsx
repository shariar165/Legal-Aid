import type { Metadata } from "next";
import { Suspense } from "react";
import { CitizenApp } from "@/components/citizen/CitizenApp";

/* One Citizen result per URL (spec 28): reload or reopen it on the same device. The job belongs to the session
   that ran it, so on another device the page says the result is not here and offers to run it again. */
export const metadata: Metadata = {
  title: "ফলাফল · যুক্তি",
  robots: { index: false, follow: false },
};

export default function CitizenResult({ params }: PageProps<"/r/[jobId]">) {
  return <Suspense fallback={null}>{params.then(({ jobId }) => <CitizenApp jobId={jobId} />)}</Suspense>;
}
