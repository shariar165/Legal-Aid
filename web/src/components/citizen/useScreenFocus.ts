"use client";

import { useEffect, useRef } from "react";

/** Move focus to a screen's heading when it mounts, so screen readers announce the new screen. */
export function useScreenFocus<T extends HTMLElement>() {
  const ref = useRef<T>(null);
  useEffect(() => {
    ref.current?.focus({ preventScroll: true });
  }, []);
  return ref;
}
