import { LOGO_SVG_BODY } from "./logo-paths";

/** The যুক্তি mark (spec 22): the matra of যু is the beam of a balance. Decorative; the name sits beside it as text. */
export function Logo({ size = 36, className }: { size?: number; className?: string }) {
  return (
    <svg
      className={className}
      width={size}
      height={size}
      viewBox="0 0 512 512"
      aria-hidden="true"
      focusable="false"
      // generated, static path data from scripts/build-logo.py, never user input
      dangerouslySetInnerHTML={{ __html: LOGO_SVG_BODY }}
    />
  );
}
