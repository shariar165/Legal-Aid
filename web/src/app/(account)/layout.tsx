import { inter, sourceSerif } from "@/lib/fonts";

/* Sign-in screens share the Counsel workspace look (English-first, Latin faces). */
export default function AccountLayout({ children }: { children: React.ReactNode }) {
  return (
    <div lang="en" className={`${inter.variable} ${sourceSerif.variable}`}>
      {children}
    </div>
  );
}
