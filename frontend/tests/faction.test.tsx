// frontend/tests/faction.test.tsx
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, render, renderHook, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import App from '../src/App';
import { FactionToggle } from '../src/components/FactionToggle';
import { FACTION_STORAGE_KEY, useFaction } from '../src/hooks/useFaction';
import { stubApi } from './fixtures';

function renderApp(): void {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  stubApi([]);
  render(
    <QueryClientProvider client={client}>
      <App />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  window.localStorage.clear();
  delete document.documentElement.dataset.faction;
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('FactionToggle', () => {
  it('marks the active faction as checked', () => {
    render(<FactionToggle value="zeon" onChange={() => undefined} />);
    expect(screen.getByRole('radio', { name: /自護/ })).toHaveAttribute('aria-checked', 'true');
    expect(screen.getByRole('radio', { name: /聯邦/ })).toHaveAttribute('aria-checked', 'false');
  });

  it('emits the clicked faction', async () => {
    const onChange = vi.fn();
    render(<FactionToggle value="federation" onChange={onChange} />);
    await userEvent.click(screen.getByRole('radio', { name: /自護/ }));
    expect(onChange).toHaveBeenCalledWith('zeon');
  });
});

describe('useFaction', () => {
  it('defaults to federation and applies it to the document element', () => {
    const { result } = renderHook(() => useFaction());
    expect(result.current[0]).toBe('federation');
    expect(document.documentElement.dataset.faction).toBe('federation');
  });

  it('persists a switch and restores it on the next mount', () => {
    const first = renderHook(() => useFaction());
    act(() => first.result.current[1]('zeon'));

    expect(document.documentElement.dataset.faction).toBe('zeon');
    expect(window.localStorage.getItem(FACTION_STORAGE_KEY)).toBe('zeon');

    first.unmount();
    const second = renderHook(() => useFaction());
    expect(second.result.current[0]).toBe('zeon');
  });

  it('treats an unknown stored value as federation', () => {
    window.localStorage.setItem(FACTION_STORAGE_KEY, 'white-base');
    const { result } = renderHook(() => useFaction());
    expect(result.current[0]).toBe('federation');
  });
});

describe('App faction theme', () => {
  it('switches the document faction from the header toggle', async () => {
    renderApp();
    expect(document.documentElement.dataset.faction).toBe('federation');

    await userEvent.click(screen.getByRole('radio', { name: /自護/ }));

    expect(document.documentElement.dataset.faction).toBe('zeon');
    expect(window.localStorage.getItem(FACTION_STORAGE_KEY)).toBe('zeon');
  });
});
