// frontend/src/pages/ImportPage.tsx
import { useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { uploadCsv } from '../api/import.api';
import { IMPORT_FRESHNESS_KEY } from '../hooks/useImportFreshness';
import { GRADES, SHOP_CODES, type Grade, type ImportResult, type ShopCode } from '../types';
import { SHOP_LABEL } from '../shops';

export function ImportPage() {
  const queryClient = useQueryClient();
  const [shop, setShop] = useState<ShopCode>('hobbyland');
  const [grade, setGrade] = useState<Grade>('hg');
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<ImportResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file || busy) return;
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      const res = await uploadCsv(shop, grade, file);
      setResult(res);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['comparisons'] }),
        queryClient.invalidateQueries({ queryKey: [IMPORT_FRESHNESS_KEY] }),
      ]);
    } catch (err) {
      setError(err instanceof Error ? err.message : '匯入失敗');
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="import-page">
      <h2>匯入 CSV</h2>
      <form onSubmit={submit} className="import-form">
        <label>
          網店
          <select value={shop} onChange={(e) => setShop(e.target.value as ShopCode)}>
            {SHOP_CODES.map((code) => (
              <option key={code} value={code}>
                {SHOP_LABEL[code]}
              </option>
            ))}
          </select>
        </label>
        <label>
          級別
          <select value={grade} onChange={(e) => setGrade(e.target.value as Grade)}>
            {GRADES.map((g) => (
              <option key={g} value={g}>
                {g.toUpperCase()}
              </option>
            ))}
          </select>
        </label>
        <label>
          CSV 檔案
          <input
            type="file"
            accept=".csv,text/csv"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          />
        </label>
        <button type="submit" disabled={!file || busy}>
          {busy ? '匯入中…' : '匯入'}
        </button>
      </form>
      {result && (
        <p className="status success">
          完成：匯入 {result.rowCount} 列{result.skipped > 0 ? `，跳過 ${result.skipped} 列` : ''}（batch #{result.batchId}）
        </p>
      )}
      {error && <p className="status error">{error}</p>}
    </section>
  );
}
