import { Inter, Source_Serif_4 } from "next/font/google";

/* Counsel mode is an English-first professional workspace: Latin faces here,
   with the root layout's Bengali fonts as the fallback for Bangla text. */
const inter = Inter({ variable: "--font-inter", subsets: ["latin"] });
const sourceSerif = Source_Serif_4({ variable: "--font-source-serif", subsets: ["latin"] });

export default function CounselLayout({ children }: { children: React.ReactNode }) {
  return (
    <div lang="en" className={`${inter.variable} ${sourceSerif.variable}`}>
      {children}
    </div>
  );
}
