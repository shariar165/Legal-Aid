/* The dalal's seat: a plain, neutral silhouette. Deliberately not a judge sticker and not a caricature. */
export function DalalAvatar({ size = 44 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 48 48" aria-hidden="true" focusable="false">
      <circle cx="24" cy="24" r="24" fill="#d9d4c7" />
      <circle cx="24" cy="19" r="8.5" fill="#8b857a" />
      <path d="M9 41c1.8-8 8-12 15-12s13.2 4 15 12a24 24 0 0 1-30 0Z" fill="#8b857a" />
    </svg>
  );
}
