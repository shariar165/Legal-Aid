import type { Metadata, Viewport } from "next";
import { Hind_Siliguri, Noto_Serif_Bengali } from "next/font/google";
import { inter, sourceSerif } from "@/lib/fonts";
import "./globals.css";

const hindSiliguri = Hind_Siliguri({
  variable: "--font-hind-siliguri",
  subsets: ["bengali", "latin"],
  weight: ["400", "500", "600", "700"],
});

const notoSerifBengali = Noto_Serif_Bengali({
  variable: "--font-noto-serif-bengali",
  subsets: ["bengali"],
  weight: ["400", "600", "700"],
});

export const metadata: Metadata = {
  title: "যুক্তি · Jukti",
  description: "চুক্তির ছবি তুলুন — সহজ ভাষায় জানুন কোথায় বিপদ আছে। Contract safety check for migrant workers.",
};

export const viewport: Viewport = {
  themeColor: "#0F4C3A",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    /* both modes share one set of faces (spec 20): Latin faces first, the Bengali ones for Bangla glyphs */
    <html lang="bn" className={`${inter.variable} ${sourceSerif.variable} ${hindSiliguri.variable} ${notoSerifBengali.variable}`}>
      {/* browser extensions (e.g. ColorZilla) add attributes to <body> before hydration */}
      <body suppressHydrationWarning>{children}</body>
    </html>
  );
}
