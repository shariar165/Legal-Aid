import type { Metadata } from "next";
import { RehearsalApp } from "@/components/rehearsal/RehearsalApp";

export const metadata: Metadata = {
  title: "মহড়া · আগে মহড়া, পরে টাকা · Ain Copilot",
  description: "দালালের সঙ্গে কথা বলার আগে নিরাপদ মহড়া দিন। Rehearse the conversation with a recruiting middleman before you pay anything.",
};

export default function RehearsalPage() {
  return <RehearsalApp />;
}
