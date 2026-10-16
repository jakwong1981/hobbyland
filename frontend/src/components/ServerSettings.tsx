// frontend/src/components/ServerSettings.tsx
import { useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { clearApiBase, getApiBase, normalizeApiBase, setApiBase } from '../api/serverConfig';

type TestState =
  | { status: 'idle' }
  | { status: 'testing' }
  | { status: 'ok' }
  | { status: 'failed'; message: string };

const TEST_PATH = '/api/imports/freshness';
const TEST_TIMEOUT_MS = 5000;

async function testServer(base: string): Promise<void> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TEST_TIMEOUT_MS);
  try {
    const res = await fetch(`${base}${TEST_PATH}`, { signal: controller.signal });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
  } finally {
    clearTimeout(timer);
  }
}

export function ServerSettings() {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [effectiveBase, setEffectiveBase] = useState(getApiBase);
  const [draft, setDraft] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [test, setTest] = useState<TestState>({ status: 'idle' });

  const applyBase = (next: string) => {
    setEffectiveBase(next);
    setError(null);
    setTest({ status: 'idle' });
    // Server changed: reset (not just clear) the cache so every mounted query
    // refetches — clear() empties the cache but leaves mounted observers
    // displaying data from the old server.
    void queryClient.resetQueries();
  };

  const handleSave = () => {
    try {
      applyBase(setApiBase(draft));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  const handleReset = () => {
    applyBase(clearApiBase());
    setDraft('');
  };

  const handleTest = async () => {
    let base: string;
    try {
      base = draft.trim() === '' ? effectiveBase : normalizeApiBase(draft);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      return;
    }
    setError(null);
    setTest({ status: 'testing' });
    try {
      await testServer(base);
      setTest({ status: 'ok' });
    } catch (e) {
      setTest({ status: 'failed', message: e instanceof Error ? e.message : String(e) });
    }
  };

  return (
    <div className="server-settings">
      <button
        type="button"
        className={open ? 'nav-btn active' : 'nav-btn'}
        aria-expanded={open}
        onClick={() => setOpen(!open)}
      >
        伺服器
      </button>
      {open && (
        <div className="server-panel" role="dialog" aria-label="伺服器地址設定">
          <p className="server-current">
            目前地址：<code>{effectiveBase === '' ? '預設（同源伺服器）' : effectiveBase}</code>
          </p>
          <input
            className="server-input"
            type="url"
            inputMode="url"
            autoComplete="off"
            spellCheck={false}
            placeholder="https://host:8089"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
          />
          <div className="server-actions">
            <button type="button" className="nav-btn" onClick={handleTest} disabled={test.status === 'testing'}>
              {test.status === 'testing' ? '測試中…' : '測試'}
            </button>
            <button type="button" className="nav-btn" onClick={handleSave}>
              儲存
            </button>
            <button type="button" className="nav-btn" onClick={handleReset}>
              重設預設
            </button>
          </div>
          {test.status === 'ok' && <p className="server-test ok">✓ 連線正常</p>}
          {test.status === 'failed' && <p className="server-test failed">✗ 連線失敗：{test.message}</p>}
          {error !== null && <p className="server-test failed">✗ {error}</p>}
        </div>
      )}
    </div>
  );
}
