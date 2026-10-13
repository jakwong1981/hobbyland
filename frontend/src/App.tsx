// frontend/src/App.tsx
import { useState } from 'react';
import { DashboardPage } from './pages/DashboardPage';
import { ImportPage } from './pages/ImportPage';
import { FactionCrest } from './components/FactionCrest';
import { FactionToggle } from './components/FactionToggle';
import { FactionWipe } from './components/FactionWipe';
import { useFaction } from './hooks/useFaction';
import { SHOP_CODES } from './types';
import { SHOP_LABEL } from './shops';

type Page = 'dashboard' | 'import';

export default function App() {
  const [page, setPage] = useState<Page>('dashboard');
  const [faction, setFaction] = useFaction();

  return (
    <div className="app-shell">
      <div className="particles" aria-hidden="true" />
      <FactionWipe faction={faction} />
      <header className="app-header">
        <span className="header-stripe" aria-hidden="true" />
        <div className="brand">
          <FactionCrest faction={faction} />
          <div className="brand-text">
            <h1>Gunpla 格價</h1>
            <p className="brand-sub">
              Price Recon // {SHOP_CODES.map((shop) => SHOP_LABEL[shop]).join(' × ')}
            </p>
          </div>
        </div>
        <div className="header-controls">
          <FactionToggle value={faction} onChange={setFaction} />
          <nav>
            <button
              className={page === 'dashboard' ? 'nav-btn active' : 'nav-btn'}
              onClick={() => setPage('dashboard')}
            >
              格價表
            </button>
            <button
              className={page === 'import' ? 'nav-btn active' : 'nav-btn'}
              onClick={() => setPage('import')}
            >
              匯入
            </button>
          </nav>
        </div>
      </header>
      <main>{page === 'dashboard' ? <DashboardPage /> : <ImportPage />}</main>
    </div>
  );
}
