// frontend/src/hooks/useProgressiveRows.ts
import { useEffect, useRef, useState } from 'react';

const DEFAULT_PAGE_SIZE = 100;
// Grow well before the user reaches the end so appending stays invisible.
const ROOT_MARGIN = '800px 0px';

/**
 * Renders a long list in growing chunks: the first `pageSize` items mount
 * immediately, and a sentinel after the list grows the window as it nears the
 * viewport. Keeps initial layout/paint cheap on low-power WebViews (the
 * dashboard's default HG view is ~1.1k rows).
 */
export function useProgressiveRows<T>(items: T[], pageSize = DEFAULT_PAGE_SIZE) {
  const [limit, setLimit] = useState(pageSize);
  const sentinelRef = useRef<HTMLDivElement | null>(null);

  // A new filter/sort result restarts the window from the first chunk.
  useEffect(() => {
    setLimit(pageSize);
  }, [items, pageSize]);

  useEffect(() => {
    if (typeof IntersectionObserver === 'undefined') return; // jsdom test env
    const el = sentinelRef.current;
    if (!el) return;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) {
          setLimit((current) => Math.min(current + pageSize, items.length));
        }
      },
      { rootMargin: ROOT_MARGIN },
    );
    observer.observe(el);
    return () => observer.disconnect();
    // Re-observing after each growth matters: observe() fires an initial
    // callback, so a sentinel still inside the margin grows the window again
    // until it is pushed clear of the viewport.
  }, [items.length, pageSize, limit]);

  return {
    shown: items.slice(0, limit),
    sentinelRef,
    hasMore: limit < items.length,
    remaining: Math.max(items.length - limit, 0),
  };
}
