import type { Metadata } from "next";
import { AccountGate } from "@/components/counsel/Account";
import { CounselStart } from "@/components/counsel/CounselStart";

export const metadata: Metadata = {
  title: "Counsel mode · Ain Copilot",
  description: "Verified legal risk memorandum with citation ledger, Virtual Bench and agent trace.",
};

export default function CounselIndex() {
  return (
    <AccountGate>
      <CounselStart />
    </AccountGate>
  );
}
