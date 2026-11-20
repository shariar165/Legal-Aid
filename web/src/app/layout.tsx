import type { Metadata, Viewport } from "next";
import { Hind_Siliguri, Noto_Serif_Bengali } from "next/font/google";
import { ThemeSync } from "@/components/shared/ThemeToggle";
import { inter, sourceSerif } from "@/lib/fonts";
import { THEME_SCRIPT } from "@/lib/theme";
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
  /* the forest bar, in each theme (spec 26) */
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#1F3D2B" },
    { media: "(prefers-color-scheme: dark)", color: "#12221A" },
  ],
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    /* both modes share one set of faces (spec 20): Latin faces first, the Bengali ones for Bangla glyphs */
    /* suppressHydrationWarning: the inline theme script sets data-theme on <html> before React hydrates (spec 26) */
    <html
      lang="bn"
      className={`${inter.variable} ${sourceSerif.variable} ${hindSiliguri.variable} ${notoSerifBengali.variable}`}
      suppressHydrationWarning
    >
      <head>
        {/* runs while the HTML is parsed, so a dark-mode reader never sees a light flash */}
        <script dangerouslySetInnerHTML={{ __html: THEME_SCRIPT }} />
      </head>
      {/* browser extensions (e.g. ColorZilla) add attributes to <body> before hydration */}
      <body suppressHydrationWarning>
        <ThemeSync />
        {children}
      </body>
    </html>
  );
}
