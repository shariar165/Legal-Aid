import { silkscreen } from "@/lib/fonts";

/* Counsel mode is an English-first professional workspace. The root layout loads the shared faces;
   only the council scene's pixel face is added here. */
export default function CounselLayout({ children }: { children: React.ReactNode }) {
  return (
    <div lang="en" className={silkscreen.variable}>
      {children}
    </div>
  );
}
