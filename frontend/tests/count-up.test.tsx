// frontend/tests/count-up.test.tsx
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, renderHook } from '@testing-library/react';
import { useCountUp } from '../src/hooks/useCountUp';

type FrameCallback = (now: number) => void;

let frames: Map<number, FrameCallback>;
let nextId: number;

function runFrame(now: number): void {
  const pending = [...frames.values()];
  frames.clear();
  act(() => pending.forEach((cb) => cb(now)));
}

function stubReducedMotion(matches: boolean): void {
  vi.spyOn(window, 'matchMedia').mockImplementation(
    (query: string) =>
      ({
        matches,
        media: query,
        onchange: null,
        addEventListener: () => undefined,
        removeEventListener: () => undefined,
        addListener: () => undefined,
        removeListener: () => undefined,
        dispatchEvent: () => false,
      }) as MediaQueryList,
  );
}

beforeEach(() => {
  frames = new Map();
  nextId = 1;
  vi.stubGlobal('requestAnimationFrame', (cb: FrameCallback) => {
    const id = nextId++;
    frames.set(id, cb);
    return id;
  });
  vi.stubGlobal('cancelAnimationFrame', (id: number) => frames.delete(id));
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe('useCountUp', () => {
  it('shows the target immediately when the user prefers reduced motion', () => {
    stubReducedMotion(true);
    const { result } = renderHook(() => useCountUp(42));
    expect(result.current).toBe(42);
    expect(frames.size).toBe(0);
  });

  it('tweens from zero to the target over the duration', () => {
    stubReducedMotion(false);
    const { result } = renderHook(() => useCountUp(100, 1000));
    expect(result.current).toBe(0);

    runFrame(0);
    runFrame(500);
    expect(result.current).toBeGreaterThan(0);
    expect(result.current).toBeLessThan(100);

    runFrame(1000);
    expect(result.current).toBe(100);
    expect(frames.size).toBe(0);
  });

  it('continues from the shown value when the target changes', () => {
    stubReducedMotion(false);
    const { result, rerender } = renderHook(({ target }) => useCountUp(target, 100), {
      initialProps: { target: 10 },
    });
    runFrame(0);
    runFrame(100);
    expect(result.current).toBe(10);

    rerender({ target: 4 });
    runFrame(200);
    expect(result.current).toBe(10);
    runFrame(300);
    expect(result.current).toBe(4);
  });

  it('cancels the pending frame on unmount', () => {
    stubReducedMotion(false);
    const { unmount } = renderHook(() => useCountUp(50));
    expect(frames.size).toBe(1);
    unmount();
    expect(frames.size).toBe(0);
  });
});
