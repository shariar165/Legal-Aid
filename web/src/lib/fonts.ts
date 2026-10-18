import { Inter, Source_Serif_4 } from "next/font/google";

/* Latin faces for the English-first workspace screens (Counsel, sign-in). The root layout's
   Bengali fonts stay the fallback for Bangla text. */
export const inter = Inter({ variable: "--font-inter", subsets: ["latin"] });
export const sourceSerif = Source_Serif_4({ variable: "--font-source-serif", subsets: ["latin"] });
