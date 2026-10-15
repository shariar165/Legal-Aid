import type { Metadata } from "next";
import { CounselStart } from "@/components/counsel/CounselStart";

export const metadata: Metadata = {
  title: "Counsel mode · Ain Copilot",
  description: "Verified legal risk memorandum with citation ledger, Virtual Bench and agent trace.",
};

export default function CounselIndex() {
  return <CounselStart />;
}
