import { inter, sourceSerif } from "@/lib/fonts";

/* Counsel mode is an English-first professional workspace: Latin faces here,
   with the root layout's Bengali fonts as the fallback for Bangla text. */
export default function CounselLayout({ children }: { children: React.ReactNode }) {
  return (
    <div lang="en" className={`${inter.variable} ${sourceSerif.variable}`}>
      {children}
    </div>
  );
}
