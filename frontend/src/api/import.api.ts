// frontend/src/api/import.api.ts
import { apiGet, apiUpload } from './client';
import type { Grade, ImportFreshness, ImportResult, ShopCode } from '../types';

export function uploadCsv(shop: ShopCode, grade: Grade, file: File): Promise<ImportResult> {
  const form = new FormData();
  form.set('shop', shop);
  form.set('grade', grade);
  form.set('file', file);
  return apiUpload<ImportResult>('/api/import', form);
}

export function fetchImportFreshness(grade: Grade): Promise<ImportFreshness> {
  return apiGet<ImportFreshness>(`/api/imports/freshness?grade=${grade}`);
}
