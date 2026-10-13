// frontend/src/hooks/useCountUp.ts
import { useEffect, useRef, useState } from 'react';
import { usePrefersReducedMotion } from './usePrefersReducedMotion';

export const COUNT_UP_DURATION_MS = 900;

function easeOutCubic(t: number): number {
  return 1 - (1 - t) ** 3;
}

// Tweens from the previously shown number, so switching grade rolls the counter
// rather than snapping back to zero first.
export function useCountUp(target: number, durationMs = COUNT_UP_DURATION_MS): number {
  const reducedMotion = usePrefersReducedMotion();
  const [value, setValue] = useState(reducedMotion ? target : 0);
  const shownRef = useRef(value);

  useEffect(() => {
    if (reducedMotion) {
      shownRef.current = target;
      setValue(target);
      return undefined;
    }

    const from = shownRef.current;
    let frame = 0;
    let start: number | null = null;

    const step = (now: number) => {
      start ??= now;
      const progress = Math.min((now - start) / durationMs, 1);
      const next = Math.round(from + (target - from) * easeOutCubic(progress));
      shownRef.current = next;
      setValue(next);
      if (progress < 1) frame = requestAnimationFrame(step);
    };

    frame = requestAnimationFrame(step);
    return () => cancelAnimationFrame(frame);
  }, [target, durationMs, reducedMotion]);

  return value;
}
